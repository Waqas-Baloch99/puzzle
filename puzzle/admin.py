from django.contrib import admin
from django.urls import path
from django.shortcuts import render, reverse
from django.utils.html import format_html
from django.contrib.admin import AdminSite
from django.core.paginator import Paginator
from django.db.models import Count, F, Value, CharField
from django.utils import timezone
import logging
import json
from datetime import timedelta
from decouple import config
import google.generativeai as genai
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile, Puzzle, Submission, RoadmapTopic, Topic, PuzzleSubmission

logger = logging.getLogger(__name__)

def roadmap_view(request):
    roadmap_topics = RoadmapTopic.objects.filter(parent__isnull=True)\
        .prefetch_related('children', 'puzzles')\
        .order_by('order')
    return render(request, 'admin/roadmap.html', {
        "roadmap_topics": roadmap_topics
    })

class CustomAdminSite(AdminSite):
    site_header = "PuzzleHub Admin"
    site_title = "PuzzleHub Admin Portal"
    index_title = "Welcome to PuzzleHub Admin Portal"
    site_url = "/"

    def get_urls(self):
        default_urls = super().get_urls()
        custom_urls = [
            path('custom-dashboard/', self.admin_view(self.custom_dashboard_view), name='custom-dashboard'),
            path('manage-users/', self.admin_view(self.manage_users_view), name='manage-users'),
            path('manage-puzzles/', self.admin_view(self.manage_puzzles_view), name='manage-puzzles'),
            path('manage-submissions/', self.admin_view(self.manage_submissions_view), name='manage-submissions'),
            path('generate-puzzles/', self.admin_view(self.generate_puzzle_view), name='generate-puzzles'),
            path('edit-puzzle/<int:puzzle_id>/', self.admin_view(self.edit_puzzle_view), name='edit-puzzle'),
            path('delete-puzzle/<int:puzzle_id>/', self.admin_view(self.delete_puzzle_view), name='delete-puzzle'),
            path('roadmap/', self.admin_view(roadmap_view), name='roadmap'),
        ]
        return custom_urls + default_urls

    def custom_dashboard_view(self, request):
        try:
            context = self.each_context(request)
            submissions_list = Submission.objects.select_related('user', 'puzzle').order_by('-submitted_at')
            paginator = Paginator(submissions_list, 10)
            page_num = request.GET.get('page', 1)
            submissions_page = paginator.get_page(page_num)

            total_users = Profile.objects.count()
            total_puzzles = Puzzle.objects.count()
            total_submissions = Submission.objects.count()
            thirty_days_ago = timezone.now() - timedelta(days=30)

            top_users = Profile.objects.filter(
                user__submission__submitted_at__gte=thirty_days_ago
            ).annotate(
                solved_count=Count('user__submission', filter=Submission.objects.filter(is_correct=True))
            ).order_by('-solved_count')[:5]

            context.update({
                'title': "Puzzle Management Dashboard",
                'submissions': submissions_page,
                'total_users': total_users,
                'total_puzzles': total_puzzles,
                'total_submissions': total_submissions,
                'top_users': top_users,
                'page_obj': submissions_page,
                'available_apps': self.get_app_list(request),
            })
            return render(request, 'admin/custom_dashboard.html', context)
        except Exception as e:
            logger.error(f"Dashboard view error: {str(e)}")
            context.update({'error': str(e)})
            return render(request, 'admin/custom_dashboard.html', context)

    def manage_users_view(self, request):
        try:
            context = self.each_context(request)
            profiles = Profile.objects.select_related('user').all()
            paginator = Paginator(profiles, 10)
            page_num = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_num)

            context.update({
                'title': "Manage Users",
                'user_profiles': page_obj,
                'page_obj': page_obj,
            })
            return render(request, 'admin/manage_users.html', context)
        except Exception as e:
            logger.error(f"Users view error: {str(e)}")
            context.update({'error': str(e)})
            return render(request, 'admin/manage_users.html', context)

    def manage_puzzles_view(self, request):
        try:
            category = request.GET.get('category', 'all')
            level = request.GET.get('level')
            puzzles = Puzzle.objects.all()

            if category != 'all':
                puzzles = puzzles.filter(category=category)
            if level:
                puzzles = puzzles.filter(level=level)

            puzzles = puzzles.order_by('-created_at')
            paginator = Paginator(puzzles, 10)
            page_num = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_num)

            context = self.each_context(request)
            context.update({
                'title': "Manage Puzzles",
                'puzzles': page_obj,
                'page_obj': page_obj,
                'active_category': category,
                'active_level': level
            })
            return render(request, 'admin/manage_puzzles.html', context)
        except Exception as e:
            logger.error(f"Puzzles view error: {str(e)}")
            context.update({'error': str(e)})
            return render(request, 'admin/manage_puzzles.html', context)

    def manage_submissions_view(self, request):
        try:
            context = self.each_context(request)
            submissions = Submission.objects.select_related('user', 'puzzle').order_by('-submitted_at')
            paginator = Paginator(submissions, 10)
            page_num = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_num)

            context.update({
                'title': "Manage Submissions",
                'submissions': page_obj,
                'page_obj': page_obj,
            })
            return render(request, 'admin/manage_submissions.html', context)
        except Exception as e:
            logger.error(f"Submissions view error: {str(e)}")
            context.update({'error': str(e)})
            return render(request, 'admin/manage_submissions.html', context)

    def generate_puzzle_view(self, request):
        try:
            context = self.each_context(request)
            context.update({'title': "Generate Puzzles"})
            
            # Get all roadmap topics, including children
            roadmap_topics = RoadmapTopic.objects.all().order_by('parent__order', 'order')
            
            # Organize topics into a hierarchical structure
            topics_dict = {}
            for topic in roadmap_topics:
                topic.indent_level = 0
                if topic.parent:
                    topic.indent_level = 1
                    # If grandparent exists, add another level
                    if topic.parent.parent:
                        topic.indent_level = 2
                topics_dict[topic.id] = topic

            context['roadmap_topics'] = roadmap_topics

            if request.method == 'POST':
                selected_topics = request.POST.getlist('topics')
                num_mcqs = int(request.POST.get('num_mcqs', 0))
                num_coding = int(request.POST.get('num_coding', 0))
                
                if not selected_topics:
                    context.update({'error': "Please select at least one topic"})
                    return render(request, 'admin/generate_puzzles.html', context)
                
                if num_mcqs == 0 and num_coding == 0:
                    context.update({'error': "Please specify at least one MCQ or coding puzzle to generate"})
                    return render(request, 'admin/generate_puzzles.html', context)

                # Configure Gemini
                genai.configure(api_key=config('GEMINI_API_KEY'))
                model = genai.GenerativeModel('gemini-2.0-flash')
                puzzles_created = 0
                valid_puzzles = []
                
                # Get existing titles for duplicate check
                existing_titles = set(Puzzle.objects.values_list('title', flat=True))

                for topic_id in selected_topics:
                    topic = RoadmapTopic.objects.get(id=topic_id)
                    
                    # Generate MCQs for the topic
                    if num_mcqs > 0:
                        prompt = f"""Return JSON only. Generate {num_mcqs} unique MCQs about {topic.title}.
                        Each question MUST be related to {topic.title} and have a detailed description.
                        Format: [{{"title": "short question", "description": "detailed explanation of the question", 
                        "options": {{"A": "option1", "B": "option2", "C": "option3", "D": "option4"}}, 
                        "correct_answer": "A/B/C/D"}}]"""
                        
                        try:
                            response = model.generate_content(prompt)
                            raw_response = response.text.strip()
                            cleaned_response = raw_response.replace('```json', '').replace('```', '')
                            puzzles_data = json.loads(cleaned_response)
                            
                            if not isinstance(puzzles_data, list):
                                puzzles_data = [puzzles_data]
                            
                            for puzzle_data in puzzles_data:
                                if not all(k in puzzle_data for k in ['title', 'description']):
                                    continue
                                
                                title = puzzle_data['title'].strip()
                                if title in existing_titles or not title:
                                    continue
                                
                                Puzzle.objects.create(
                                    title=title,
                                    description=puzzle_data['description'].strip(),
                                    category='PY',
                                    level='beginner',
                                    puzzle_type='MCQ',
                                    xp_reward=50,
                                    test_cases=puzzle_data.get('options', {}),
                                    solution=puzzle_data.get('correct_answer', ''),
                                    roadmap_topic=topic
                                )
                                
                                puzzles_created += 1
                                existing_titles.add(title)
                                valid_puzzles.append(title)
                        except Exception as e:
                            logger.error(f"Error generating MCQs for topic {topic.title}: {str(e)}")
                    
                    # Generate coding puzzles for the topic
                    if num_coding > 0:
                        prompt = f"""Return JSON only. Generate {num_coding} unique intermediate Python coding puzzles about {topic.title}.
                        Each puzzle MUST be related to {topic.title} and have a detailed description.
                        Format: [{{"title": "short name", "description": "detailed problem statement with requirements", 
                        "test_cases": {{"test1": {{"input": "example", "output": "result"}}, 
                        "test2": {{"input": "example2", "output": "result2"}}}}}}]"""
                        
                        try:
                            response = model.generate_content(prompt)
                            raw_response = response.text.strip()
                            cleaned_response = raw_response.replace('```json', '').replace('```', '')
                            puzzles_data = json.loads(cleaned_response)
                            
                            if not isinstance(puzzles_data, list):
                                puzzles_data = [puzzles_data]
                            
                            for puzzle_data in puzzles_data:
                                if not all(k in puzzle_data for k in ['title', 'description']):
                                    continue
                                
                                title = puzzle_data['title'].strip()
                                if title in existing_titles or not title:
                                    continue
                                
                                Puzzle.objects.create(
                                    title=title,
                                    description=puzzle_data['description'].strip(),
                                    category='PY',
                                    level='intermediate',
                                    puzzle_type='CODE',
                                    xp_reward=100,
                                    test_cases=puzzle_data.get('test_cases', {}),
                                    solution='',
                                    roadmap_topic=topic
                                )
                                
                                puzzles_created += 1
                                existing_titles.add(title)
                                valid_puzzles.append(title)
                        except Exception as e:
                            logger.error(f"Error generating coding puzzles for topic {topic.title}: {str(e)}")

                if puzzles_created == 0:
                    context.update({'error': "No valid puzzles could be created"})
                else:
                    context.update({
                        'success': f"Successfully created {puzzles_created} puzzles"
                    })
                return render(request, 'admin/generate_puzzles.html', context)

            return render(request, 'admin/generate_puzzles.html', context)

        except Exception as e:
            logger.error(f"Puzzle generation error: {str(e)}")
            context.update({'error': str(e)})
            return render(request, 'admin/generate_puzzles.html', context)

    def edit_puzzle_view(self, request, puzzle_id):
        try:
            puzzle = Puzzle.objects.get(id=puzzle_id)
            context = self.each_context(request)
            context['title'] = f"Edit {puzzle.title}"

            if request.method == 'POST':
                # Existing edit logic remains the same
                # Ensure you update roadmap_topic relationship if needed
                pass

            return render(request, 'admin/edit_puzzle.html', context)
        except Puzzle.DoesNotExist:
            context.update({'error': "Puzzle not found"})
            return render(request, 'admin/edit_puzzle.html', context)

    def delete_puzzle_view(self, request, puzzle_id):
        try:
            puzzle = Puzzle.objects.get(id=puzzle_id)
            context = self.each_context(request)
            
            if request.method == 'POST':
                puzzle.delete()
                context['success'] = f"Deleted {puzzle.title}"
                return render(request, 'admin/delete_puzzle.html', context)
            
            context['puzzle'] = puzzle
            return render(request, 'admin/delete_puzzle.html', context)
        except Exception as e:
            context['error'] = str(e)
            return render(request, 'admin/delete_puzzle.html', context)

class RoadmapTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'parent', 'order', 'puzzle_count', 'full_path')
    list_filter = ('parent',)
    list_editable = ('order',)
    search_fields = ('title', 'description')
    ordering = ('order',)

    def full_path(self, obj):
        return obj.get_full_path()
    full_path.short_description = "Hierarchy Path"

    def puzzle_count(self, obj):
        count = obj.puzzles.count()
        url = reverse('admin:puzzle_puzzle_changelist') + f'?roadmap_topic__id__exact={obj.id}'
        return format_html('<a href="{}">{} Puzzles</a>', url, count)
    puzzle_count.short_description = 'Puzzles'

class PuzzleAdmin(admin.ModelAdmin):
    list_display = ('title', 'roadmap_topic', 'category', 'level', 'puzzle_type', 'points')
    list_filter = ('category', 'level', 'roadmap_topic')
    search_fields = ('title', 'description', 'roadmap_topic__title')
    raw_id_fields = ('roadmap_topic',)
    date_hierarchy = 'created_at'

    def save_model(self, request, obj, form, change):
        # Ensure MCQ puzzles have properly formatted test cases
        if obj.puzzle_type == 'MCQ':
            # If test_cases is a string, try to parse it as JSON
            if isinstance(obj.test_cases, str):
                try:
                    obj.test_cases = json.loads(obj.test_cases)
                except json.JSONDecodeError:
                    # If not valid JSON, create a default structure
                    obj.test_cases = {
                        'A': 'Option A',
                        'B': 'Option B',
                        'C': 'Option C',
                        'D': 'Option D'
                    }
            # If test_cases is empty, set default structure
            elif not obj.test_cases:
                obj.test_cases = {
                    'A': 'Option A',
                    'B': 'Option B',
                    'C': 'Option C',
                    'D': 'Option D'
                }
            
            # Ensure solution is one of the test case keys
            if obj.solution not in obj.test_cases.keys():
                obj.solution = list(obj.test_cases.keys())[0]

        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.puzzle_type == 'MCQ':
            form.base_fields['test_cases'].help_text = (
                'For MCQ puzzles, enter a JSON object with options like: '
                '{"A": "First option", "B": "Second option", ...}'
            )
            form.base_fields['solution'].help_text = (
                'For MCQ puzzles, enter the key of the correct answer (e.g., "A", "B", etc.)'
            )
        return form

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'xp', 'level')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('xp', 'level')

class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'puzzle', 'is_correct', 'submitted_at')
    list_filter = ('is_correct',)
    raw_id_fields = ('user', 'puzzle')

# Register with custom admin site
custom_admin_site = CustomAdminSite(name='custom_admin')
custom_admin_site.register(RoadmapTopic, RoadmapTopicAdmin)
custom_admin_site.register(Puzzle, PuzzleAdmin)
custom_admin_site.register(Profile, ProfileAdmin)
custom_admin_site.register(Submission, SubmissionAdmin)

# Register the Profile model
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'profile'

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'level', 'puzzle_type', 'xp_reward', 'is_active')
    list_filter = ('category', 'level', 'puzzle_type', 'is_active')
    search_fields = ('title', 'description')
    ordering = ('roadmap_topic__order', 'created_at')

@admin.register(RoadmapTopic)
class RoadmapTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'parent', 'order')
    list_filter = ('parent',)
    search_fields = ('title', 'description')
    ordering = ('order', 'title')

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'prerequisite')
    list_filter = ('prerequisite',)
    search_fields = ('name', 'description')
    ordering = ('order',)

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'puzzle', 'is_correct', 'submitted_at')
    list_filter = ('is_correct', 'puzzle__category', 'puzzle__level')
    search_fields = ('user__username', 'puzzle__title')
    ordering = ('-submitted_at',)

@admin.register(PuzzleSubmission)
class PuzzleSubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'puzzle', 'is_correct', 'xp_earned', 'submitted_at')
    list_filter = ('is_correct', 'puzzle__category', 'puzzle__level')
    search_fields = ('user__username', 'puzzle__title')
    ordering = ('-submitted_at',)