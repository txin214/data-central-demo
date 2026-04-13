# Accounts App - User Authentication

This Django app handles user authentication including registration, login, logout, and profile management.

## Features

- **User Registration**: Create new user accounts with username, email, first name, and last name
- **User Login**: Secure authentication with username and password
- **User Logout**: Safe session termination
- **User Profile**: View user account information
- **Responsive Design**: Bootstrap-styled forms that work on all devices

## URLs

- `/accounts/login/` - User login page
- `/accounts/logout/` - User logout (redirects to home)
- `/accounts/register/` - User registration page
- `/accounts/profile/` - User profile page (requires login)

## Views

- `CustomLoginView` - Handles user login with redirect support
- `CustomLogoutView` - Handles user logout
- `RegisterView` - Handles user registration with auto-login
- `profile_view` - Displays user profile information

## Forms

- `CustomUserCreationForm` - Enhanced registration form with additional fields

## Templates

- `login.html` - Login form with Bootstrap styling
- `register.html` - Registration form with additional fields
- `profile.html` - User profile display

## Settings

The following settings are configured in `settings.py`:

```python
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
```

## Usage

1. Users can register new accounts at `/accounts/register/`
2. Existing users can log in at `/accounts/login/`
3. Authenticated users can view their profile at `/accounts/profile/`
4. Users can log out using the logout link in the navigation

## Security

- Uses Django's built-in authentication system
- Password validation follows Django's security guidelines
- CSRF protection enabled on all forms
- Login required for profile access
