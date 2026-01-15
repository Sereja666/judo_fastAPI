// static/js/auth.js
function logout() {
    // 1. Удаляем из localStorage
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');

    // 2. Удаляем cookie
    document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;";
    document.cookie = "session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;";

    // 3. Делаем запрос на серверный logout
    fetch('/api/auth/jwt-logout', { method: 'GET' })
        .then(() => {
            // 4. Перенаправляем на выбор входа
            window.location.href = '/choose-login';
        });

    return false; // Предотвращаем переход по ссылке
}