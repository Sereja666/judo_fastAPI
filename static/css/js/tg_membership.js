// static/js/tg_membership.js

let lastUpdateTime = new Date();

// Обновить время последнего обновления
function updateLastUpdateTime() {
    const now = new Date();
    const diff = Math.floor((now - lastUpdateTime) / 1000);

    if (diff < 60) {
        document.getElementById('lastUpdate').textContent = 'только что';
    } else if (diff < 3600) {
        document.getElementById('lastUpdate').textContent = `${Math.floor(diff / 60)} мин назад`;
    } else {
        document.getElementById('lastUpdate').textContent = now.toLocaleTimeString();
    }
}

// Обновить данные
function refreshData() {
    location.reload();
}

// Показать всех подтвержденных пользователей
function showAllApproved() {
    window.location.href = '/admin/users/approved?limit=100';
}

// Подтверждение пользователя
async function approveUser(userId) {
    try {
        const response = await fetch(`/admin/users/${userId}/approve`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.status === 'success') {
            alert(result.message);
            // Удаляем карточку пользователя
            const userCard = document.getElementById(`user-${userId}`);
            if (userCard) {
                userCard.remove();
            }
            // Обновляем счетчики
            location.reload();
        } else {
            alert('Ошибка: ' + (result.message || 'Неизвестная ошибка'));
        }
    } catch (error) {
        alert('Ошибка сети: ' + error);
    }
}

// Подтвердить отклонение
async function confirmReject() {
    const userId = document.getElementById('rejectUserId').value;
    const reason = document.getElementById('rejectReason').value;

    try {
        const url = `/admin/users/${userId}/reject${reason ? '?reason=' + encodeURIComponent(reason) : ''}`;
        const response = await fetch(url, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.status === 'success') {
            alert(result.message);
            // Удаляем карточку пользователя
            const userCard = document.getElementById(`user-${userId}`);
            if (userCard) {
                userCard.remove();
            }
            // Закрываем модальное окно
            const modal = bootstrap.Modal.getInstance(document.getElementById('rejectModal'));
            modal.hide();
            // Обновляем счетчики
            location.reload();
        } else {
            alert('Ошибка: ' + (result.message || 'Неизвестная ошибка'));
        }
    } catch (error) {
        alert('Ошибка сети: ' + error);
    }
}

// Переключить уведомления
async function toggleNotification(userId, type, button) {
    try {
        const response = await fetch(`/admin/users/${userId}/toggle-notifications?notification_type=${type}`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.status === 'success') {
            // Переключаем класс active у кнопки
            button.classList.toggle('active');

            // Меняем стиль кнопки
            if (button.classList.contains('active')) {
                button.classList.remove('btn-outline-secondary');
                button.classList.add('btn-success');
            } else {
                button.classList.remove('btn-success');
                button.classList.add('btn-outline-secondary');
            }
        } else {
            alert('Ошибка: ' + (result.message || 'Неизвестная ошибка'));
        }
    } catch (error) {
        alert('Ошибка сети: ' + error);
    }
}

// Показать модальное окно поиска ученика
function searchStudentModal() {
    const modal = new bootstrap.Modal(document.getElementById('searchStudentModal'));
    modal.show();
}

// Выполнить поиск ученика
async function performStudentSearch() {
    const searchInput = document.getElementById('studentSearchInput').value;

    if (searchInput.length < 2) {
        alert('Введите хотя бы 2 символа для поиска');
        return;
    }

    try {
        const response = await fetch(`/admin/search/student?name=${encodeURIComponent(searchInput)}`);
        const students = await response.json();

        const resultsDiv = document.getElementById('searchResults');

        if (students.length === 0) {
            resultsDiv.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> Ученики не найдены
                </div>
            `;
            return;
        }

        let html = '<div class="list-group">';
        students.forEach(student => {
            const activeBadge = student.active
                ? '<span class="badge bg-success">Активен</span>'
                : '<span class="badge bg-danger">Неактивен</span>';

            html += `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${student.name}</h6>
                        ${activeBadge}
                    </div>
                    <small class="text-muted">
                        ID: ${student.id}
                        ${student.birthday ? '| Дата рождения: ' + student.birthday : ''}
                    </small>
                </div>
            `;
        });
        html += '</div>';

        resultsDiv.innerHTML = html;
    } catch (error) {
        alert('Ошибка поиска: ' + error);
    }
}

// Инициализация обработчиков событий
function initEventListeners() {
    // Обработчики для кнопок подтверждения
    document.querySelectorAll('.approve-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const userId = this.dataset.userId;
            const userName = this.dataset.userName || 'пользователя';

            if (confirm(`Подтвердить пользователя "${userName}"?`)) {
                approveUser(userId);
            }
        });
    });

    // Обработчики для кнопок отклонения
    document.querySelectorAll('.reject-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const userId = this.dataset.userId;
            const userName = this.dataset.userName || 'пользователя';

            document.getElementById('rejectUserId').value = userId;
            document.getElementById('rejectUserName').textContent = userName;

            const modal = new bootstrap.Modal(document.getElementById('rejectModal'));
            modal.show();
        });
    });

    // Обработчики для переключателей уведомлений
    document.querySelectorAll('.news-toggle').forEach(btn => {
        btn.addEventListener('click', function() {
            toggleNotification(this.dataset.userId, 'news', this);
        });
    });

    document.querySelectorAll('.pays-toggle').forEach(btn => {
        btn.addEventListener('click', function() {
            toggleNotification(this.dataset.userId, 'pays', this);
        });
    });

    document.querySelectorAll('.info-toggle').forEach(btn => {
        btn.addEventListener('click', function() {
            toggleNotification(this.dataset.userId, 'info', this);
        });
    });

    // Обработчик для кнопки подтверждения отклонения
    const confirmRejectBtn = document.getElementById('confirmReject');
    if (confirmRejectBtn) {
        confirmRejectBtn.addEventListener('click', confirmReject);
    }
}

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    initEventListeners();

    // Обновляем время при загрузке
    updateLastUpdateTime();
    setInterval(updateLastUpdateTime, 60000);
});