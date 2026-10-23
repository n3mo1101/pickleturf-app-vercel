from django.contrib import admin
from .models import OpenPlaySession, OpenPlayParticipant

class ParticipantInline(admin.TabularInline):
    model  = OpenPlayParticipant
    extra  = 0
    fields = ('user', 'status', 'joined_at')
    readonly_fields = ('joined_at',)

@admin.register(OpenPlaySession)
class OpenPlaySessionAdmin(admin.ModelAdmin):
    list_display  = ('title', 'date', 'start_time', 'capacity', 'spots_remaining', 'status')
    list_filter   = ('status', 'date')
    search_fields = ('title',)
    inlines       = [ParticipantInline]

@admin.register(OpenPlayParticipant)
class OpenPlayParticipantAdmin(admin.ModelAdmin):
    list_display  = ('user', 'session', 'status', 'joined_at')
    list_filter   = ('status',)
    search_fields = ('user__email',)