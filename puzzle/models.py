from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class RoadmapTopic(models.Model):
    title = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, 
                             null=True, blank=True, 
                             related_name='children')
    order = models.PositiveIntegerField(default=0, 
                                      help_text="Ordering position in hierarchy")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = "Roadmap Topic"
        verbose_name_plural = "Roadmap Topics"

    def __str__(self):
        return self.title

    def get_full_path(self):
        path = []
        obj = self
        while obj:
            path.append(obj.title)
            obj = obj.parent
        return ' → '.join(reversed(path))

class Topic(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    order = models.IntegerField(default=0)
    prerequisite = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['order']

class Puzzle(models.Model):
    CATEGORIES = [
        ('PY', 'Python'),
        ('AI', 'AI/ML'),
        ('DS', 'Data Science'),
    ]
    
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert'),
    ]

    PUZZLE_TYPES = [
        ('MCQ', 'Multiple Choice Question'),
        ('CODE', 'Coding Puzzle'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=2, choices=CATEGORIES)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    puzzle_type = models.CharField(max_length=4, choices=PUZZLE_TYPES)
    points = models.IntegerField(default=10)
    test_cases = models.JSONField(default=dict)
    solution = models.TextField()
    expected_output = models.TextField(blank=True, null=True)
    starter_code = models.TextField(blank=True, null=True)
    roadmap_topic = models.ForeignKey(
        RoadmapTopic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='puzzles'
    )
    topic = models.ForeignKey(Topic, related_name='puzzles', on_delete=models.CASCADE, null=True, blank=True)
    order = models.IntegerField(default=0)
    difficulty = models.IntegerField(default=1)  # 1: Easy, 2: Medium, 3: Hard
    xp_reward = models.IntegerField(default=100)  # Changed from points_reward to xp_reward
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['roadmap_topic__order', 'created_at']

    def __str__(self):
        return f"{self.title} ({self.get_puzzle_type_display()})"

    def save(self, *args, **kwargs):
        # Auto-set puzzle type based on level
        self.puzzle_type = 'MCQ' if self.level == 'beginner' else 'CODE'
        super().save(*args, **kwargs)

class Submission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    code = models.TextField(null=True, blank=True)
    answer = models.CharField(max_length=500, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    feedback = models.JSONField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'puzzle']
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.user.username} - {self.puzzle.title}"

    def save(self, *args, **kwargs):
        if self.puzzle.puzzle_type == 'MCQ':
            self.is_correct = self.answer == self.puzzle.solution
        else:
            # Add your code execution logic here
            self.is_correct = self.answer == self.puzzle.expected_output
        super().save(*args, **kwargs)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    avatar_url = models.URLField(max_length=200, blank=True)
    bio = models.TextField(blank=True, help_text='Tell us about yourself', null=True)
    github_username = models.CharField(max_length=39, blank=True, help_text='Your GitHub username', null=True)
    linkedin_url = models.URLField(blank=True, help_text='Your LinkedIn profile URL', null=True)
    solved_puzzles = models.ManyToManyField('Puzzle', blank=True)

    def add_xp(self, amount):
        """Add XP to user profile and update level"""
        self.xp += amount
        # Update level based on XP thresholds
        new_level = 1 + (self.xp // 1000)  # Level up every 1000 XP
        if new_level != self.level:
            self.level = new_level
        self.save()

    def __str__(self):
        return f"{self.user.username}'s profile - Level {self.level} ({self.xp} XP)"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class ChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    response = models.TextField(null=True, blank=True)
    is_bot = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    model_used = models.CharField(max_length=50, default='gemini-pro')
    voice_message = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

class PuzzleSubmission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    submitted_answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    xp_earned = models.IntegerField(default=0)
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_correct and not PuzzleSubmission.objects.filter(
            user=self.user, puzzle=self.puzzle, is_correct=True
        ).exists():
            # Only award XP for first correct submission
            self.xp_earned = self.puzzle.xp_reward
            self.user.profile.add_xp(self.xp_earned)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s submission for {self.puzzle.title}"

    class Meta:
        ordering = ['-submitted_at']