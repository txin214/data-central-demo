from django.db import models
from django.contrib.auth.models import User, Permission
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    """Extended user profile with additional personal information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Imported/account metadata
    usercode = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    zip = models.CharField(max_length=20, blank=True)
    cellphone = models.CharField(max_length=50, blank=True)
    deskphone = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=150, blank=True)
    usertype = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    PRONOUN_CHOICES = [
        ('he/him', 'He/Him'),
        ('she/her', 'She/Her'),
        ('they/them', 'They/Them'),
        ('other', 'Other'),
    ]
    pronoun = models.CharField(max_length=20, choices=PRONOUN_CHOICES, blank=True)
    location = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class Role(models.Model):
    """Custom roles for users (e.g., Office Staff, Field Worker, Manager, Admin)"""
    
    # Role type choices based on CategoryID from usernames.csv
    TYPE_CHOICES = [
        ('DES', 'Designer'),
        ('CAR', 'MSN Carpenter'),
        ('ACCT', 'Accounting'),
        ('OFF', 'Office Staff'),
        ('CARP2', 'BFD Carpenter'),
        ('INA', 'Inactive'),
        ('SHP', 'Top Shop Staff'),
        ('NONE', 'No Category'),
        ('TOPI', 'Top Installer'),
        ('SUB', 'Sub Contractor'),
        ('DLVR', 'Deliveries'),
        ('MNGR', 'Department Manager'),
        ('PLU', 'Plumber'),
        ('COR', 'Coordinator'),
        ('DEV1', 'Developer'),
        ('SLS', 'Sales'),
        ('GM', 'General Manager'),
    ]
    
    # Access level choices based on TUSERTYPECODE from usernames.csv
    ACCESS_LEVEL_CHOICES = [
        ('SAL', 'Sales'),
        ('SYS', 'System'),
        ('CAR', 'Carpenter'),
        ('ACC', 'Account'),
        ('OFF', 'Office'),
        ('CLI', 'Client'),
        ('MNG', 'Manager'),
    ]
    
    name = models.CharField(max_length=100, choices=ACCESS_LEVEL_CHOICES, 
                           help_text="System access level (TUSERTYPECODE)")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='NONE',
                           help_text="Job function category (CategoryID)")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['type', 'name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        # Ensure unique combination of type and name
        unique_together = ['type', 'name']
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.get_name_display()}"
    
    def get_full_name(self):
        """Return the full display name combining type and name"""
        return f"{self.get_type_display()} ({self.get_name_display()})"
    
    @classmethod
    def get_roles_by_type(cls, role_type):
        """Get all roles of a specific type"""
        return cls.objects.filter(type=role_type, is_active=True)
    
    @classmethod
    def get_roles_by_access_level(cls, access_level):
        """Get all roles with a specific access level"""
        return cls.objects.filter(name=access_level, is_active=True)


class UserRole(models.Model):
    """Many-to-many relationship between Users and Roles"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_roles')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'role']
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
    
    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


class RolePermission(models.Model):
    """Many-to-many relationship between Roles and Permissions"""
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_permissions')
    
    class Meta:
        unique_together = ['role', 'permission']
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
    
    def __str__(self):
        return f"{self.role.name} - {self.permission.name}"


# Helper methods for User model
def user_has_role(self, role_name):
    """Check if user has a specific role"""
    return self.user_roles.filter(role__name=role_name, is_active=True).exists()

def user_get_roles(self):
    """Get all active roles for user"""
    return self.user_roles.filter(is_active=True).select_related('role')

def user_has_permission_via_role(self, permission_codename):
    """Check if user has permission through any of their roles"""
    return self.user_roles.filter(
        is_active=True,
        role__role_permissions__permission__codename=permission_codename
    ).exists()

# Add methods to User model
User.add_to_class('has_role', user_has_role)
User.add_to_class('get_roles', user_get_roles)
User.add_to_class('has_permission_via_role', user_has_permission_via_role)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a profile when a user is created"""
    if kwargs.get("raw", False):
        return
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Automatically save the profile when the user is saved"""
    if kwargs.get("raw", False):
        return
    if hasattr(instance, 'profile'):
        instance.profile.save()
