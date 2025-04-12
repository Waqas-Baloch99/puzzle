from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.db.models import Exists, OuterRef, Count, Q, Sum
from .models import Puzzle, Submission, Profile, ChatMessage, RoadmapTopic, Topic
from .forms import PuzzleSubmissionForm, SignUpForm, EmailAuthenticationForm, UserProfileForm
import google.generativeai as genai
from decouple import config
import json
import logging
import re
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import os
import time
from django.conf import settings
from gtts import gTTS
import uuid
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.chains import LLMChain

# Configure logging
logger = logging.getLogger(__name__)

# Configure Gemini API globally
genai.configure(api_key=config('GEMINI_API_KEY'))
gemini_pro = genai.GenerativeModel('gemini-2.0-flash')
gemini_mini = genai.GenerativeModel('gemini-2.0-flash')

@login_required
def index(request):
    # Get user's progress
    total_puzzles = Puzzle.objects.count()
    solved_puzzles = Submission.objects.filter(
        user=request.user,
        is_correct=True
    ).count()
    
    # Calculate completion percentage
    completion_percentage = (solved_puzzles / total_puzzles * 100) if total_puzzles > 0 else 0
    
    # Get user's recent activity
    recent_submissions = Submission.objects.filter(
        user=request.user
    ).order_by('-submitted_at')[:5]
    
    # Get user's XP and level
    user_profile = request.user.profile
    current_xp = user_profile.xp
    current_level = user_profile.level
    xp_for_next_level = (current_level + 1) * 1000
    xp_progress = (current_xp % 1000) / 10  # Convert to percentage
    
    context = {
        'total_puzzles': total_puzzles,
        'solved_puzzles': solved_puzzles,
        'completion_percentage': round(completion_percentage, 1),
        'recent_submissions': recent_submissions,
        'current_xp': current_xp,
        'current_level': current_level,
        'xp_for_next_level': xp_for_next_level,
        'xp_progress': xp_progress
    }
    
    return render(request, 'puzzle/index.html', context)

@login_required
def puzzles(request):
    topic_id = request.GET.get('topic')
    if topic_id:
        puzzles = Puzzle.objects.filter(roadmap_topic__id=topic_id).order_by('roadmap_topic__order', 'order')
    else:
        puzzles = Puzzle.objects.all().order_by('roadmap_topic__order', 'order')
    
    # Get the solved puzzles for the current user
    solved_puzzle_ids = Submission.objects.filter(
        user=request.user,
        is_correct=True
    ).values_list('puzzle_id', flat=True)
    
    # Add solved status to each puzzle
    for puzzle in puzzles:
        puzzle.is_solved = puzzle.id in solved_puzzle_ids
    
    topics = RoadmapTopic.objects.filter(parent__isnull=True).order_by('order')
    
    context = {
        'puzzles': puzzles,
        'topics': topics,
        'selected_topic': int(topic_id) if topic_id else None
    }
    return render(request, 'puzzle/puzzles.html', context)

@login_required
def puzzle_detail(request, puzzle_id):
    """Display puzzle details and redirect to solve page for submission."""
    puzzle = get_object_or_404(Puzzle, pk=puzzle_id)
    user_profile = request.user.profile
    existing_submission = Submission.objects.filter(user=request.user, puzzle=puzzle).first()

    context = {
        'puzzle': puzzle,
        'submission': existing_submission,
        'is_solved': puzzle in user_profile.solved_puzzles.all(),
        'type_display': 'MCQ' if puzzle.puzzle_type == 'mcq' else 'Coding',
        'topic': puzzle.roadmap_topic
    }
    return render(request, 'puzzle/detail.html', context)

@login_required
def roadmap_view(request):
    """Display the Python learning roadmap with interactive visualization."""
    topics = RoadmapTopic.objects.all().select_related('parent')
    user_profile = request.user.profile
    completed_puzzles = user_profile.solved_puzzles.all()
    
    nodes = []
    edges = []
    
    for topic in topics:
        # Check completion status - a topic is completed if all its puzzles are solved
        topic_puzzles = topic.puzzles.all()
        is_completed = topic_puzzles.exists() and all(puzzle in completed_puzzles for puzzle in topic_puzzles)
        
        # Create node with improved styling
        node = {
            "id": topic.id,
            "label": topic.title,
            "color": {
                "background": "#2ecc71" if is_completed else "#cccccc",
                "border": "#27ae60" if is_completed else "#bbbbbb",
                "highlight": {
                    "background": "#27ae60" if is_completed else "#dddddd",
                    "border": "#219a52" if is_completed else "#aaaaaa"
                }
            },
            "puzzle_ids": [puzzle.id for puzzle in topic_puzzles],
            "title": f"<div style='max-width: 200px; padding: 8px;'>"
                    f"<strong>{topic.title}</strong><br/>"
                    f"{'✓ Completed' if is_completed else 'Not completed yet'}"
                    f"</div>"
        }
        nodes.append(node)
        
        # Create edge if there's a parent
        if topic.parent:
            edges.append({
                "from": topic.parent.id,
                "to": topic.id,
                "arrows": "to",
                "color": {
                    "color": "#2c3e50",
                    "highlight": "#34495e"
                }
            })
    
    roadmap_data = {
        "nodes": nodes,
        "edges": edges
    }
    
    return render(request, 'puzzle/roadmap.html', {
        "roadmap_data": roadmap_data
    })

from django.urls import reverse

@login_required
def solve_puzzle(request, puzzle_id):
    """Handle puzzle solving with direct validation for MCQs and LLM validation for coding puzzles."""
    puzzle = get_object_or_404(Puzzle, pk=puzzle_id)
    user_profile = request.user.profile
    existing_submission = Submission.objects.filter(user=request.user, puzzle=puzzle).first()
    stored_code = request.session.get(f'retry_code_{puzzle_id}', '')

    # Debug logging
    logger.debug(f"Puzzle type: {puzzle.puzzle_type}")
    logger.debug(f"Test cases: {puzzle.test_cases}")
    logger.debug(f"Solution: {puzzle.solution}")

    # Get next puzzle in the same topic
    next_puzzle = None
    if puzzle.roadmap_topic:
        next_puzzle = Puzzle.objects.filter(
            roadmap_topic=puzzle.roadmap_topic,
            id__gt=puzzle.id,
            is_active=True
        ).exclude(id__in=user_profile.solved_puzzles.values_list('id', flat=True)).order_by('id').first()
        
        # If no next puzzle in current topic, get first puzzle from next topic
        if not next_puzzle:
            next_topic = RoadmapTopic.objects.filter(
                order__gt=puzzle.roadmap_topic.order
            ).order_by('order').first()
            if next_topic:
                next_puzzle = Puzzle.objects.filter(
                    roadmap_topic=next_topic,
                    is_active=True
                ).exclude(id__in=user_profile.solved_puzzles.values_list('id', flat=True)).order_by('id').first()

    if request.method == 'POST':
        if puzzle.puzzle_type == 'MCQ':  # Changed from 'mcq' to 'MCQ'
            # Handle MCQ submission
            answer = request.POST.get('answer')
            if answer:
                submission = existing_submission if existing_submission else Submission(user=request.user, puzzle=puzzle)
                submission.answer = answer
                submission.is_correct = answer == puzzle.solution
                submission.save()
                
                if submission.is_correct:
                    if not existing_submission or not existing_submission.is_correct:
                        user_profile.xp += puzzle.xp_reward
                        user_profile.solved_puzzles.add(puzzle)
                        user_profile.save()
                        messages.success(request, f'🎉 Correct answer! You earned {puzzle.xp_reward} XP!')
                    else:
                        messages.success(request, '✅ Correct answer! You already completed this puzzle.')
                else:
                    messages.error(request, '❌ Incorrect answer. Try again!')
        else:
            # Handle coding puzzle submission
            form = PuzzleSubmissionForm(request.POST, puzzle=puzzle)
            if form.is_valid():
                submission = existing_submission if existing_submission else Submission(user=request.user, puzzle=puzzle)
                submission.code = form.cleaned_data['code']
                submission.status = 'pending'

                validation_prompt = f"""
                    You are a Python code validator. Evaluate this solution and respond with a JSON object.
                    
                    Problem: {puzzle.description}
                    Expected Output/Behavior: {puzzle.test_cases if puzzle.test_cases else 'No specific test cases provided.'}
                    
                    User's Solution:
                    ```python
                    {submission.code}
                    ```
                    
                    Validate the code and return a JSON object with:
                    - "is_correct": true if the solution is correct, false otherwise
                    - "feedback": one short line of feedback (error message if incorrect, success message if correct)
                    
                    Keep the feedback concise and specific. If incorrect, point out the main issue only.
                """

                try:
                    response = gemini_mini.generate_content(validation_prompt)
                    response_text = response.text.strip()
                    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(1)
                    
                    validation_result = json.loads(response_text)
                    
                    submission.feedback = validation_result.get('feedback', '')
                    submission.is_correct = validation_result.get('is_correct', False)
                    
                    if submission.is_correct:
                        submission.status = 'completed'
                        submission.save()
                        
                        if not existing_submission or not existing_submission.is_correct:
                            user_profile.xp += puzzle.xp_reward
                            user_profile.solved_puzzles.add(puzzle)
                            user_profile.save()
                            messages.success(request, f'🎉 Correct solution! You earned {puzzle.xp_reward} XP!')
                        else:
                            messages.success(request, '✅ Correct solution! You already completed this puzzle.')
                    else:
                        submission.status = 'failed'
                        submission.save()
                        messages.error(request, f'❌ {submission.feedback}')
                        request.session[f'retry_code_{puzzle_id}'] = submission.code
                        
                except Exception as e:
                    logger.error(f"Validation error: {str(e)}", exc_info=True)
                    messages.error(request, "An error occurred during validation. Please try again.")
                    submission.status = 'error'
                    submission.save()
                    request.session[f'retry_code_{puzzle_id}'] = submission.code

    else:
        # GET request - show form
        initial_data = {'code': stored_code} if stored_code else {}
        form = PuzzleSubmissionForm(puzzle=puzzle, initial=initial_data)

    # Convert test_cases to options for MCQ
    mcq_options = []
    selected_answer = None
    if puzzle.puzzle_type == 'MCQ' and puzzle.test_cases:  # Changed from 'mcq' to 'MCQ'
        try:
            # Ensure test_cases is a dictionary
            if isinstance(puzzle.test_cases, str):
                options_dict = json.loads(puzzle.test_cases)
            else:
                options_dict = puzzle.test_cases
            
            # Debug logging
            logger.debug(f"MCQ options dict: {options_dict}")
            
            mcq_options = [{'key': str(key), 'value': str(value)} for key, value in options_dict.items()]
            
            # Get selected answer from existing submission
            if existing_submission:
                selected_answer = existing_submission.answer
        except Exception as e:
            logger.error(f"Error processing MCQ options: {str(e)}")
            mcq_options = []

    context = {
        'puzzle': puzzle,
        'form': form if puzzle.puzzle_type != 'MCQ' else None,  # Changed from 'mcq' to 'MCQ'
        'submission': existing_submission,
        'next_puzzle': next_puzzle,
        'type_display': 'Multiple Choice' if puzzle.puzzle_type == 'MCQ' else 'Coding',  # Updated display text
        'mcq_options': mcq_options,
        'selected_answer': selected_answer,
        'is_solved': existing_submission and existing_submission.is_correct
    }
    
    return render(request, 'puzzle/solve.html', context)

@login_required
def submit_solution(request, puzzle_id):
    """Handle puzzle solution submission (alternative entry point)."""
    return puzzle_detail(request, puzzle_id)  # Reuse puzzle_detail view logic

def leaderboard(request):
    """Display the top 10 users by points."""
    top_users = Profile.objects.all().order_by('-xp')[:10]
    return render(request, 'puzzle/leaderboard.html', {'top_users': top_users})

class CustomLoginView(LoginView):
    """Custom login view using email authentication."""
    form_class = EmailAuthenticationForm
    template_name = 'registration/login.html'
    redirect_authenticated_user = True
    success_url = reverse_lazy('puzzle:index')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Welcome back, {self.request.user.username}!')
        return response

def signup(request):
    """Handle user signup with custom form."""
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been created.")
            return redirect('puzzle:index')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def profile(request):
    user_profile = request.user.profile
    submissions = Submission.objects.filter(user=request.user).order_by('-submitted_at')
    
    total_xp = user_profile.xp
    puzzles_solved = submissions.filter(is_correct=True).count()
    current_level = user_profile.level
    
    # Calculate XP progress for current level
    xp_for_next_level = (current_level + 1) * 1000
    xp_progress = (total_xp % 1000) / 10  # Convert to percentage
    
    # Get recent activity
    recent_activity = submissions.order_by('-submitted_at')[:10]
    
    context = {
        'user_profile': user_profile,
        'submissions': submissions,
        'total_xp': total_xp,
        'puzzles_solved': puzzles_solved,
        'current_level': current_level,
        'xp_progress': xp_progress,
        'xp_for_next_level': xp_for_next_level,
        'recent_activity': recent_activity
    }
    return render(request, 'puzzle/profile.html', context)

def logout_view(request):
    """Handle user logout."""
    if request.method == 'POST':
        logout(request)
        messages.info(request, "You have been logged out successfully.")
    return redirect('puzzle:index')

@login_required
def ai_assistant(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            is_voice_input = data.get('is_voice_input', False)
            voice_mode = data.get('voice_mode', False)

            if not message:
                return JsonResponse({'error': 'Message cannot be empty'})

            # Save user message
            ChatMessage.objects.create(
                user=request.user,
                content=message,
                is_bot=False,
                voice_message=is_voice_input,
                timestamp=timezone.now()
            )

            # Create a structured prompt for Gemini with app context
            prompt = f"""You are a helpful Python programming assistant for PyPuzzle, a Python learning platform. 
            Please provide a structured response with the following sections:

            PyPuzzle Context:
            - Multiple puzzle types: MCQ, Code Writing, Debugging, Algorithm Implementation
            - Difficulty levels: Beginner, Intermediate, Advanced
            - Topics: Python syntax, Data structures, Functions, OOP, Algorithms
            - Features: Progress tracking, Achievements, Interactive code execution

            Response Structure:
            1. Explanation: Provide a clear and concise explanation of the answer in paragraph form.
            2. Key Points: List the important points using markdown bullet points (*). Each point should be a single, clear statement.
            3. Code Examples: Present any relevant code examples within markdown code blocks (```python ... ```). Ensure each example is self-contained and clearly demonstrates the concept. Add a brief caption before each code block.
            4. Notes: Include any important notes or warnings using markdown blockquotes (>). Each note should start with "! Note:" or "! Warning:".

            For voice input, keep the explanation conversational and avoid the specific formatting.
            For text input, adhere strictly to the structured format.

            User's {'voice message' if is_voice_input else 'question'}: {message}
            """

            # Generate response using the existing Gemini model
            response = gemini_pro.generate_content(prompt)
            response_text = response.text.strip()

            # Format the response for voice if needed
            speech_text = None
            if voice_mode:
                # Create a simplified version for speech
                lines = response_text.split('\n')
                speech_lines = []
                for line in lines:
                    if not line.startswith(('*', '```', '>', '!', '##')):
                        speech_lines.append(line)
                speech_text = ' '.join(speech_lines)

            # Save assistant response
            ChatMessage.objects.create(
                user=request.user,
                content=response_text,
                is_bot=True,
                voice_message=is_voice_input,
                timestamp=timezone.now()
            )

            return JsonResponse({
                'message': response_text,
                'speech_text': speech_text,
                'is_voice': is_voice_input
            })

        except Exception as e:
            logger.error(f"Error in AI assistant: {str(e)}")
            return JsonResponse({'error': str(e)})

    return render(request, 'puzzle/ai_assistant.html')

@login_required
def update_profile(request):
    """Update user profile information."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('puzzle:profile')
    else:
        form = UserProfileForm(instance=request.user.profile)
    
    return render(request, 'puzzle/update_profile.html', {
        'form': form,
        'user': request.user
    })

@login_required
def chat(request):
    """Handle chat messages from the virtual assistant."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            
            # Process the message and generate a response using Gemini 2.0 Flash
            try:
                response = gemini_pro.generate_content(message)
                response_text = response.text.strip()
                
                # Return the response
                return JsonResponse({
                    'message': response_text,
                    'timestamp': timezone.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error generating AI response: {str(e)}")
                return JsonResponse({
                    'error': 'Failed to generate response. Please try again.'
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def roadmap(request):
    topics = RoadmapTopic.objects.all().order_by('order')
    
    # Get solved puzzles for the user
    solved_puzzles = Submission.objects.filter(
        user=request.user,
        is_correct=True
    ).values_list('puzzle_id', flat=True)
    
    # Add progress information to each topic
    for topic in topics:
        topic_puzzles = topic.puzzles.all()
        total_puzzles = topic_puzzles.count()
        solved_count = topic_puzzles.filter(id__in=solved_puzzles).count()
        
        topic.total_puzzles = total_puzzles
        topic.solved_puzzles = solved_count
        topic.progress = (solved_count / total_puzzles * 100) if total_puzzles > 0 else 0
    
    context = {
        'topics': topics
    }
    
    return render(request, 'puzzle/roadmap.html', context)

@login_required
def process_voice_input(request):
    if request.method == 'POST' and request.FILES.get('audio'):
        try:
            audio_file = request.FILES['audio']
            
            # Save the audio file temporarily
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f'voice_input_{request.user.id}_{int(time.time())}.wav')
            
            with open(temp_path, 'wb') as f:
                f.write(audio_file.read())
            
            # TODO: Implement actual speech-to-text processing here
            # For now, we'll return a mock response
            # You can integrate with services like Google Cloud Speech-to-Text or Azure Speech Services
            
            # Clean up the temporary file
            os.remove(temp_path)
            
            return JsonResponse({
                'text': 'This is a mock response. Please implement actual speech-to-text processing.',
                'success': True
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'success': False
            }, status=500)
    
    return JsonResponse({
        'error': 'Invalid request',
        'success': False
    }, status=400)

@login_required
def save_session_history(request):
    """Save chat session history to the database."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            messages = data.get('messages', [])
            
            # Save each message to the database
            for msg in messages:
                ChatMessage.objects.create(
                    user=request.user,
                    content=msg.get('content', ''),
                    is_bot=msg.get('is_bot', False),
                    timestamp=timezone.now()
                )
            
            return JsonResponse({
                'success': True,
                'message': 'Session history saved successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error saving session history: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to save session history'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Method not allowed'
    }, status=405)

