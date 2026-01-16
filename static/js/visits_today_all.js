// ============================================
// visits_today_api.js
// ============================================
const visitsTodayApi = {
    async loadPlaces() {
        try {
            const response = await fetch('/visits-today/get-places');
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка загрузки мест:', error);
            throw error;
        }
    },

    async loadTrainings(placeId) {
        try {
            const response = await fetch(`/visits-today/get-trainings/${placeId}`);
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка загрузки тренировок:', error);
            throw error;
        }
    },

    async loadStudents(scheduleId) {
        try {
            const response = await fetch(`/visits-today/get-students/${scheduleId}`);
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка загрузки студентов:', error);
            throw error;
        }
    },

    async searchStudent(query) {
        try {
            const response = await fetch(`/visits-today/search-extra-student?query=${encodeURIComponent(query)}`);
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка поиска:', error);
            throw error;
        }
    },

    async saveAttendance(data) {
        try {
            const response = await fetch('/visits-today/save-attendance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка сохранения:', error);
            throw error;
        }
    },

    async getAttendanceStatus(scheduleId) {
        try {
            const response = await fetch(`/visits-today/get-attendance-status/${scheduleId}`);
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка получения статуса:', error);
            throw error;
        }
    }
};

// ============================================
// visits_today_ui.js
// ============================================
const visitsTodayUI = {
    showStep(step) {
        document.querySelectorAll('.visits-step').forEach(el => {
            el.classList.add('d-none');
        });
        const stepElement = document.getElementById(`step${step}`);
        if (stepElement) {
            stepElement.classList.remove('d-none');
        }
    },

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

    createStudentItem(student, isSelected = false) {
        const item = document.createElement('div');
        item.className = `student-item ${isSelected ? 'selected' : ''} fade-in`;
        item.innerHTML = `
            <div class="student-checkbox ${isSelected ? 'checked' : ''}">
                ${isSelected ? '✓' : ''}
            </div>
            <div class="student-name">${student.display_name}</div>
        `;
        return item;
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

// ============================================
// visits_today_main.js
// ============================================
const visitsToday = {
    state: {
        currentStep: 1,
        selectedPlace: null,
        selectedTraining: null,
        scheduleId: null,
        selectedStudents: new Set(),
        extraStudents: new Map(),
        searchTimeout: null
    },

    init() {
        console.log('Инициализация системы посещений...');
        this.loadPlaces();
        this.setupEventListeners();
    },

    setupEventListeners() {
        const searchInput = document.getElementById('search-student');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleSearchInput(e.target.value);
            });
        }

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#search-results') && !e.target.closest('#search-student')) {
                this.hideSearchResults();
            }
        });
    },

    async loadPlaces() {
        try {
            visitsTodayUI.showLoading('places-list', 'Загружаем места тренировок...');
            const places = await visitsTodayApi.loadPlaces();

            const placesList = document.getElementById('places-list');
            if (!placesList) {
                console.error('Элемент places-list не найден');
                return;
            }

            placesList.innerHTML = '';

            if (places.length === 0) {
                visitsTodayUI.showEmptyList('places-list', 'Сегодня нет тренировок', 'calendar-times');
                return;
            }

            places.forEach(place => {
                const button = visitsTodayUI.createPlaceButton(place);
                button.onclick = () => this.selectPlace(place);
                placesList.appendChild(button);
            });

        } catch (error) {
            console.error('Ошибка загрузки мест:', error);
            visitsTodayUI.showError('Не удалось загрузить места тренировок');
        }
    },

    selectPlace(place) {
        this.state.selectedPlace = place;
        this.state.currentStep = 2;

        const placeTitle = document.getElementById('place-title');
        if (placeTitle) {
            placeTitle.textContent = place.name;
        }

        visitsTodayUI.showStep(2);
        this.loadTrainings(place.id);
    },

    async loadTrainings(placeId) {
        try {
            visitsTodayUI.showLoading('trainings-list', 'Загружаем тренировки...');
            const trainings = await visitsTodayApi.loadTrainings(placeId);

            const trainingsList = document.getElementById('trainings-list');
            if (!trainingsList) {
                console.error('Элемент trainings-list не найден');
                return;
            }

            trainingsList.innerHTML = '';

            if (trainings.length === 0) {
                visitsTodayUI.showEmptyList('trainings-list', 'На сегодня нет тренировок в этом месте', 'clock');
                return;
            }

            trainings.forEach(training => {
                const button = visitsTodayUI.createTrainingButton(training);
                button.onclick = () => this.selectTraining(training);
                trainingsList.appendChild(button);
            });

        } catch (error) {
            console.error('Ошибка загрузки тренировок:', error);
            visitsTodayUI.showError('Не удалось загрузить тренировки');
        }
    },

    selectTraining(training) {
        this.state.selectedTraining = training;
        this.state.scheduleId = training.id;
        this.state.currentStep = 3;

        const trainingTitle = document.getElementById('training-title');
        const trainingTime = document.getElementById('training-time');

        if (trainingTitle) trainingTitle.textContent = training.sport_name;
        if (trainingTime) trainingTime.textContent = `${training.time_start} - ${training.time_end}`;

        visitsTodayUI.showStep(3);
        this.loadStudents(training.id);
    },

    async loadStudents(scheduleId) {
        try {
            visitsTodayUI.showLoading('students-list', 'Загружаем студентов...');
            const students = await visitsTodayApi.loadStudents(scheduleId);

            const studentsList = document.getElementById('students-list');
            if (!studentsList) {
                console.error('Элемент students-list не найден');
                return;
            }

            studentsList.innerHTML = '';

            if (students.length === 0) {
                visitsTodayUI.showEmptyList('students-list', 'На этой тренировке нет записанных студентов', 'user-slash');
                return;
            }

            this.state.selectedStudents.clear();

            students.forEach(student => {
                const isSelected = student.is_visited;
                const item = visitsTodayUI.createStudentItem(student, isSelected);

                if (isSelected) {
                    this.state.selectedStudents.add(student.id);
                }

                item.onclick = () => this.toggleStudent(student, item);
                studentsList.appendChild(item);
            });

            this.updateSelectedCount();
            this.renderExtraStudents();

        } catch (error) {
            console.error('Ошибка загрузки студентов:', error);
            visitsTodayUI.showError('Не удалось загрузить студентов');
        }
    },

    toggleStudent(student, item) {
        const checkbox = item.querySelector('.student-checkbox');

        if (this.state.selectedStudents.has(student.id)) {
            this.state.selectedStudents.delete(student.id);
            item.classList.remove('selected');
            checkbox.classList.remove('checked');
            checkbox.innerHTML = '';
        } else {
            this.state.selectedStudents.add(student.id);
            item.classList.add('selected');
            checkbox.classList.add('checked');
            checkbox.innerHTML = '✓';
        }

        this.updateSelectedCount();
    },

    handleSearchInput(query) {
        if (this.state.searchTimeout) {
            clearTimeout(this.state.searchTimeout);
        }

        if (query.trim().length < 2) {
            this.hideSearchResults();
            return;
        }

        this.state.searchTimeout = setTimeout(() => {
            this.searchExtraStudent(query);
        }, 300);
    },

    async searchExtraStudent(query) {
        try {
            const results = await visitsTodayApi.searchStudent(query);
            this.showSearchResults(results);
        } catch (error) {
            console.error('Ошибка поиска:', error);
        }
    },

    showSearchResults(results) {
        const resultsContainer = document.getElementById('search-results');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = '';

        if (results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="text-center p-3 text-muted">
                    Ничего не найдено
                </div>
            `;
        } else {
            results.forEach(student => {
                const item = visitsTodayUI.createSearchResultItem(student);
                item.onclick = () => this.addExtraStudent(student);
                resultsContainer.appendChild(item);
            });
        }

        resultsContainer.style.display = 'block';
    },

    hideSearchResults() {
        const resultsContainer = document.getElementById('search-results');
        if (resultsContainer) {
            resultsContainer.style.display = 'none';
        }
    },

    addExtraStudent(student) {
        if (this.state.extraStudents.has(student.id)) {
            visitsTodayUI.showWarning('Этот ученик уже добавлен');
            return;
        }

        this.state.extraStudents.set(student.id, student);
        this.renderExtraStudents();
        this.updateSelectedCount();

        const searchInput = document.getElementById('search-student');
        if (searchInput) {
            searchInput.value = '';
        }

        this.hideSearchResults();
        visitsTodayUI.showSuccess('Ученик добавлен');
    },

    removeExtraStudent(studentId) {
        this.state.extraStudents.delete(studentId);
        this.renderExtraStudents();
        this.updateSelectedCount();
    },

    renderExtraStudents() {
        const container = document.getElementById('extra-students-list');
        if (!container) return;

        container.innerHTML = '';

        if (this.state.extraStudents.size === 0) {
            container.innerHTML = `
                <div class="text-center text-muted p-3">
                    <i class="fas fa-user-plus me-2"></i>
                    Добавьте учеников вне расписания
                </div>
            `;
            return;
        }

        this.state.extraStudents.forEach((student, id) => {
            const item = visitsTodayUI.createExtraStudentItem(student);

            const removeBtn = item.querySelector('.remove-btn');
            if (removeBtn) {
                removeBtn.onclick = (e) => {
                    e.stopPropagation();
                    this.removeExtraStudent(id);
                };
            }

            container.appendChild(item);
        });
    },

    async saveAttendance() {
        if (this.state.selectedStudents.size === 0 && this.state.extraStudents.size === 0) {
            visitsTodayUI.showError('Выберите хотя бы одного ученика');
            return;
        }

        try {
            const data = {
                schedule_id: this.state.scheduleId,
                student_ids: Array.from(this.state.selectedStudents),
                extra_students: Array.from(this.state.extraStudents.values()),
                trainer_id: 1
            };

            const result = await visitsTodayApi.saveAttendance(data);

            if (result.status === 'success') {
                visitsTodayUI.showSuccess(`Сохранено ${result.saved_count} посещений`);

                await this.loadStudents(this.state.scheduleId);

                this.state.extraStudents.clear();
                this.renderExtraStudents();

            } else {
                visitsTodayUI.showError(result.message || 'Ошибка сохранения');
            }

        } catch (error) {
            console.error('Ошибка сохранения:', error);
            visitsTodayUI.showError('Не удалось сохранить посещения');
        }
    },

    async showAttendanceStatus() {
        try {
            const statusData = await visitsTodayApi.getAttendanceStatus(this.state.scheduleId);
            visitsTodayUI.showAttendanceStatusModal(statusData);
        } catch (error) {
            console.error('Ошибка получения статуса:', error);
            visitsTodayUI.showError('Не удалось получить статус посещений');
        }
    },

    updateSelectedCount() {
        const selectedCount = this.state.selectedStudents.size;
        const extraCount = this.state.extraStudents.size;
        visitsTodayUI.updateSelectedCount(selectedCount, extraCount);
    },

    backToStep1() {
        this.state.selectedPlace = null;
        this.state.selectedTraining = null;
        this.state.selectedStudents.clear();
        this.state.extraStudents.clear();
        this.state.currentStep = 1;

        visitsTodayUI.showStep(1);
        this.loadPlaces();
    },

    backToStep2() {
        this.state.selectedTraining = null;
        this.state.selectedStudents.clear();
        this.state.extraStudents.clear();
        this.state.currentStep = 2;

        visitsTodayUI.showStep(2);
        this.renderExtraStudents();
    }
};