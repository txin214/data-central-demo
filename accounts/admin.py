from django.contrib import admin
from .models import UserProfile, Role, UserRole, RolePermission

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'location', 'created_at']
    list_filter = ['created_at', 'gender']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'location']

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['get_full_name', 'type', 'name', 'description', 'is_active', 'created_at']
    list_filter = ['type', 'name', 'is_active', 'created_at']
    search_fields = ['name', 'type', 'description']
    ordering = ['type', 'name']
    fieldsets = (
        ('Role Information', {
            'fields': ('type', 'name', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'assigned_at', 'assigned_by', 'is_active']
    list_filter = ['role', 'is_active', 'assigned_at']
    search_fields = ['user__username', 'role__name', 'assigned_by__username']
    ordering = ['-assigned_at']

@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ['role', 'permission', 'granted_at', 'granted_by']
    list_filter = ['role', 'permission__content_type', 'granted_at']
    search_fields = ['role__name', 'permission__name', 'granted_by__username']
    ordering = ['role', 'permission']
