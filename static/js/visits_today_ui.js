// visits_today_main.js - основная логика приложения
const visitsToday = {
    // Состояние приложения
    state: {
        currentStep: 1,
        selectedPlace: null,
        selectedTraining: null,
        scheduleId: null,
        selectedStudents: new Set(),
        extraStudents: new Map(),
        searchTimeout: null
    },

    // Инициализация
    init() {
        this.loadPlaces();
        this.setupEventListeners();
    },

    // Настройка обработчиков событий
    setupEventListeners() {
        // Поиск студентов при вводе
        const searchInput = document.getElementById('search-student');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleSearchInput(e.target.value);
            });
        }

        // Закрытие результатов поиска при клике вне
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#search-results') && !e.target.closest('#search-student')) {
                this.hideSearchResults();
            }
        });
    },

    // Загрузка мест тренировок
    async loadPlaces() {
        try {
            visitsTodayUI.showLoading('places-list', 'Загружаем места тренировок...');
            const places = await visitsTodayApi.loadPlaces();

            const placesList = document.getElementById('places-list');
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
            visitsTodayUI.showError('Не удалось загрузить места тренировок');
        }
    },

    // Выбор места
    selectPlace(place) {
        this.state.selectedPlace = place;
        this.state.currentStep = 2;

        document.getElementById('place-title').textContent = place.name;
        visitsTodayUI.showStep(2);
        this.loadTrainings(place.id);
    },

    // Загрузка тренировок
    async loadTrainings(placeId) {
        try {
            visitsTodayUI.showLoading('trainings-list', 'Загружаем тренировки...');
            const trainings = await visitsTodayApi.loadTrainings(placeId);

            const trainingsList = document.getElementById('trainings-list');
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
            visitsTodayUI.showError('Не удалось загрузить тренировки');
        }
    },

    // Выбор тренировки
    selectTraining(training) {
        this.state.selectedTraining = training;
        this.state.scheduleId = training.id;
        this.state.currentStep = 3;

        document.getElementById('training-title').textContent = training.sport_name;
        document.getElementById('training-time').textContent = `${training.time_start} - ${training.time_end}`;
        visitsTodayUI.showStep(3);
        this.loadStudents(training.id);
    },

    // Загрузка студентов
    async loadStudents(scheduleId) {
        try {
            visitsTodayUI.showLoading('students-list', 'Загружаем студентов...');
            const students = await visitsTodayApi.loadStudents(scheduleId);

            const studentsList = document.getElementById('students-list');
            studentsList.innerHTML = '';

            if (students.length === 0) {
                visitsTodayUI.showEmptyList('students-list', 'На этой тренировке нет записанных студентов', 'user-slash');
                return;
            }

            // Сбрасываем выбранных студентов
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
            visitsTodayUI.showError('Не удалось загрузить студентов');
        }
    },

    // Переключение студента
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

    // Обработка ввода в поиске
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

    // Поиск дополнительного студента
    async searchExtraStudent(query) {
        try {
            const results = await visitsTodayApi.searchStudent(query);
            this.showSearchResults(results);
        } catch (error) {
            console.error('Ошибка поиска:', error);
        }
    },

    // Показать результаты поиска
    showSearchResults(results) {
        const resultsContainer = document.getElementById('search-results');
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

    // Скрыть результаты поиска
    hideSearchResults() {
        const resultsContainer = document.getElementById('search-results');
        resultsContainer.style.display = 'none';
    },

    // Добавить дополнительного студента
    addExtraStudent(student) {
        if (this.state.extraStudents.has(student.id)) {
            visitsTodayUI.showWarning('Этот ученик уже добавлен');
            return;
        }

        this.state.extraStudents.set(student.id, student);
        this.renderExtraStudents();
        this.updateSelectedCount();

        // Очищаем поиск
        document.getElementById('search-student').value = '';
        this.hideSearchResults();

        visitsTodayUI.showSuccess('Ученик добавлен');
    },

    // Удалить дополнительного студента
    removeExtraStudent(studentId) {
        this.state.extraStudents.delete(studentId);
        this.renderExtraStudents();
        this.updateSelectedCount();
    },

    // Отобразить дополнительных студентов
    renderExtraStudents() {
        const container = document.getElementById('extra-students-list');
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

            // Добавляем обработчик для кнопки удаления
            const removeBtn = item.querySelector('.remove-btn');
            removeBtn.onclick = (e) => {
                e.stopPropagation();
                this.removeExtraStudent(id);
            };

            container.appendChild(item);
        });
    },

    // Сохранение посещений
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
                trainer_id: 1 // TODO: Получить из сессии
            };

            const result = await visitsTodayApi.saveAttendance(data);

            if (result.status === 'success') {
                visitsTodayUI.showSuccess(`Сохранено ${result.saved_count} посещений`);

                // Обновляем список студентов
                await this.loadStudents(this.state.scheduleId);

                // Очищаем дополнительных студентов
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

    // Показать статус посещений
    async showAttendanceStatus() {
        try {
            const statusData = await visitsTodayApi.getAttendanceStatus(this.state.scheduleId);
            visitsTodayUI.showAttendanceStatusModal(statusData);
        } catch (error) {
            console.error('Ошибка получения статуса:', error);
            visitsTodayUI.showError('Не удалось получить статус посещений');
        }
    },

    // Обновить счетчик выбранных
    updateSelectedCount() {
        const selectedCount = this.state.selectedStudents.size;
        const extraCount = this.state.extraStudents.size;
        visitsTodayUI.updateSelectedCount(selectedCount, extraCount);
    },

    // Назад к шагу 1
    backToStep1() {
        this.state.selectedPlace = null;
        this.state.selectedTraining = null;
        this.state.selectedStudents.clear();
        this.state.extraStudents.clear();
        this.state.currentStep = 1;

        visitsTodayUI.showStep(1);
        this.loadPlaces();
    },

    // Назад к шагу 2
    backToStep2() {
        this.state.selectedTraining = null;
        this.state.selectedStudents.clear();
        this.state.extraStudents.clear();
        this.state.currentStep = 2;

        visitsTodayUI.showStep(2);
        this.renderExtraStudents();
    }
};