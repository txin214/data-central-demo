from django.contrib import messages


class ClearMessagesOnAdminLoginMiddleware:
    """
    Middleware to clear messages when accessing Django admin login page
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if this is the admin login page
        if request.path == '/admin/login/' or request.path == '/admin/login':
            # Clear messages from session storage directly
            # This prevents messages from persisting and showing on the login page
            try:
                # Get the messages storage
                storage = messages.get_messages(request)
                # Mark all messages as used/consumed
                storage.used = True
                # Also clear from session if using session storage
                if hasattr(request, 'session'):
                    # Remove messages from session
                    request.session.pop('_messages', None)
            except Exception:
                # If there's any error, just continue
                pass
        
        response = self.get_response(request)
        return response

