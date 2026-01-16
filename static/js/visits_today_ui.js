// visits_today_ui.js - UI функции и утилиты
const visitsTodayUI = {
    // Показать шаг
    showStep(step) {
        document.querySelectorAll('.visits-step').forEach(el => {
            el.classList.add('d-none');
        });
        const stepElement = document.getElementById(`step${step}`);
        if (stepElement) {
            stepElement.classList.remove('d-none');
        }
    },

    // Показать уведомление
    showToast(message, type = 'info') {
        // Удаляем существующие уведомления
        const existingToasts = document.querySelectorAll('.visits-toast');
        existingToasts.forEach(toast => toast.remove());

        const toast = document.createElement('div');
        toast.className = `visits-toast alert alert-${type} position-fixed`;
        toast.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 250px;
            animation: fadeIn 0.3s;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border-radius: 8px;
        `;

        const icon = type === 'success' ? 'check-circle' :
                    type === 'warning' ? 'exclamation-triangle' :
                    type === 'danger' ? 'times-circle' : 'info-circle';

        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${icon} me-2 fs-5"></i>
                <span>${message}</span>
            </div>
        `;

        document.body.appendChild(toast);

        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.transition = 'opacity 0.3s';
                toast.style.opacity = '0';
                setTimeout(() => {
                    if (toast.parentNode) toast.remove();
                }, 300);
            }
        }, 3000);
    },

    showError(message) {
        this.showToast(message, 'danger');
    },

    showSuccess(message) {
        this.showToast(message, 'success');
    },

    showWarning(message) {
        this.showToast(message, 'warning');
    },

    createPlaceButton(place) {
        const button = document.createElement('button');
        button.className = 'btn place-btn fade-in';
        button.innerHTML = `
            <i class="fas fa-map-marker-alt"></i>
            <span>${place.name}</span>
        `;
        return button;
    },

    createTrainingButton(training) {
        const button = document.createElement('button');
        button.className = 'btn training-btn fade-in';
        button.innerHTML = `
            <i class="fas fa-clock"></i>
            <div>
                <div><strong>${training.display}</strong></div>
            </div>
        `;
        return button;
    },


    createStudentItem(student, isSelected = false, isNarrowScreen = false) {
        const item = document.createElement('div');
        item.className = `student-item ${isSelected ? 'selected' : ''} fade-in`;
        item.dataset.studentId = student.id;

        // Определяем формат имени в зависимости от ширины экрана
        let displayName;
        let showBirthYear = !isNarrowScreen;

        if (isNarrowScreen) {
            // На узких экранах: только фамилия и первая буква имени
            displayName = this.formatNameForNarrowScreen(student.name);
        } else {
            // На широких экранах: фамилия и инициалы
            displayName = this.formatStudentName(student.name);
        }

        item.innerHTML = `
            <div class="student-checkbox ${isSelected ? 'checked' : ''}">
                ${isSelected ? '✓' : ''}
            </div>
            <div class="student-info force-single-line">
                <span class="belt-emoji">${student.belt_emoji || '⚪️'}</span>
                <span class="student-text" title="${student.name}${student.birth_year ? ` (${student.birth_year})` : ''}">
                    ${displayName}
                </span>
                ${showBirthYear && student.birth_year ? `<span class="birth-year">${student.birth_year}</span>` : ''}
            </div>
        `;

        return item;
    },

    formatNameForNarrowScreen(fullName) {
        if (!fullName) return '';

        // Убираем год рождения
        let name = fullName.replace(/\d{4}/g, '').trim();
        const parts = name.split(/\s+/);

        if (parts.length >= 2) {
            // На узких экранах: только фамилия и первая буква имени
            const lastName = parts[0];
            const firstNameInitial = parts[1].charAt(0) + '.';
            return `${lastName} ${firstNameInitial}`;
        }

        // Если только фамилия
        return parts[0] || '';
    },

    formatStudentName(fullName) {
    if (!fullName) return '';

    // Убираем год рождения если он есть в имени
    let name = fullName.replace(/\d{4}/g, '').trim();

    // Форматируем для компактного отображения
    const parts = name.split(/\s+/);

    if (parts.length >= 2) {
        // Фамилия + инициалы
        const lastName = parts[0];
        const initials = parts.slice(1)
            .map(word => word.charAt(0) + '.')
            .join('');
        return `${lastName} ${initials}`;
    }

    // Если короткое имя
    return name;
},

    formatStudentNameForMobile(student) {
    if (!student.name) return '';

    // Вариант 1: Фамилия + инициалы
    const nameParts = student.name.trim().split(/\s+/);
    if (nameParts.length >= 2) {
        const lastName = nameParts[0];
        const initials = nameParts.slice(1)
            .map(word => word.charAt(0) + '.')
            .join('');
        return `${lastName} ${initials}`;
    }

    // Вариант 2: Ограничение длины
    if (student.name.length > 20) {
        return student.name.substring(0, 18) + '...';
    }

    return student.name;
},

    createSearchResultItem(student) {
        const item = document.createElement('div');
        item.className = 'search-result-item fade-in';
        item.innerHTML = student.display || student.name;
        return item;
    },

    createExtraStudentItem(student) {
        const item = document.createElement('div');
        item.className = 'extra-student-item fade-in';
        item.innerHTML = `
            <span>${student.display || student.name}</span>
            <button class="remove-btn" data-id="${student.id}">
                <i class="fas fa-times"></i>
            </button>
        `;
        return item;
    },

    updateSelectedCount(selectedCount, extraCount) {
        const total = selectedCount + extraCount;
        const badge = document.getElementById('selected-count');
        if (badge) {
            badge.textContent = total;
            badge.className = `badge ${total > 0 ? 'bg-success' : 'bg-primary'} ms-2`;
        }
    },

    showLoading(containerId, message = 'Загрузка...') {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Загрузка...</span>
                    </div>
                    <p class="mt-2 text-muted">${message}</p>
                </div>
            `;
        }
    },

    showEmptyList(containerId, message = 'Ничего не найдено', icon = 'info-circle') {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-${icon} fa-2x text-muted mb-3"></i>
                    <p class="text-muted">${message}</p>
                </div>
            `;
        }
    },

    showAttendanceStatusModal(statusData) {
        const content = document.getElementById('status-content');
        if (!content) return;

        content.innerHTML = `
            <div class="mb-3">
                <h6>${statusData.training_info.place_name}</h6>
                <p class="mb-1">Группа ${statusData.training_info.time_start}-${statusData.training_info.time_end}</p>
                <p class="mb-3"><small class="text-muted">(${statusData.training_info.sport_name})</small></p>
            </div>

            <div class="status-list mb-3">
                <h6>Присутствуют:</h6>
                ${statusData.present_students.map(s => `
                    <div class="status-present">${s.display}</div>
                `).join('')}
            </div>

            ${statusData.absent_students.length > 0 ? `
                <h6>Отсутствуют:</h6>
                <div class="status-list mb-3">
                    ${statusData.absent_students.map(s => `
                        <div class="status-absent">${s.display}</div>
                    `).join('')}
                </div>
            ` : ''}

            <div class="alert alert-info mt-3">
                <div class="d-flex justify-content-between">
                    <span>Всего:</span>
                    <strong>${statusData.stats.total} чел.</strong>
                </div>
                <div class="d-flex justify-content-between">
                    <span>Присутствуют:</span>
                    <strong>${statusData.stats.present} чел.</strong>
                </div>
                <div class="d-flex justify-content-between">
                    <span>Отсутствуют:</span>
                    <strong>${statusData.stats.absent} чел.</strong>
                </div>
            </div>
        `;

        const modalElement = document.getElementById('statusModal');
        if (modalElement) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        }
    }
};