def user_role(request):
    """Expose role flags to all templates."""
    if request.user.is_authenticated:
        return {
            'is_admin_or_staff': request.user.is_admin_or_staff,
            'user_role': request.user.role,
        }
    return {'is_admin_or_staff': False, 'user_role': None}