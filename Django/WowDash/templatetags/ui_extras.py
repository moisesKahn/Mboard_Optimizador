from django import template

register = template.Library()

@register.filter
def user_initials(user):
    """Devuelve 2 letras: inicial del nombre y del apellido; si no hay, del username.
    Siempre en mayúsculas. Si falta alguna, duplica la disponible (p.ej. 'AA').
    """
    try:
        first = (user.first_name or '').strip()
        last = (user.last_name or '').strip()
        if first and last:
            return (first[0] + last[0]).upper()
        if first:
            return (first[0] + first[1:2] or first[0]).upper()[:2] if len(first) >= 2 else (first[0]*2).upper()
        if last:
            return (last[0] + last[1:2] or last[0]).upper()[:2] if len(last) >= 2 else (last[0]*2).upper()
        username = (getattr(user, 'username', '') or '').strip()
        if username:
            # Tomar primera y última letra del username si es posible
            if len(username) >= 2:
                return (username[0] + username[-1]).upper()
            return (username[0]*2).upper()
    except Exception:
        pass
    return 'US'
