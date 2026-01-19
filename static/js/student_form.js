// static/js/student_form.js
class StudentFormManager {
    constructor() {
        console.log('StudentFormManager инициализирован');
        this.form = document.getElementById('studentForm');
        this.messageContainer = document.getElementById('message');

        if (!this.form) {
            console.error('Форма studentForm не найдена!');
            return;
        }

        console.log('Форма найдена:', this.form);
        this.initialize();
    }

    initialize() {
        console.log('Настраиваю обработчики событий');
        this.setupEventListeners();
        this.setupFieldHighlighting();
    }

    setupEventListeners() {
        if (this.form) {
            console.log('Добавляю обработчик submit');
            this.form.addEventListener('submit', (e) => {
                console.log('Форма отправлена!');
                e.preventDefault();
                this.saveStudent(e);
            });
        }
    }

    setupFieldHighlighting() {
        // Добавляем обработчики на поля формы для подсветки изменений
        const fields = this.form.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            field.addEventListener('change', () => {
                this.highlightField(field);
            });
        });
    }

    highlightField(field) {
        field.classList.add('highlight');
        setTimeout(() => {
            field.classList.remove('highlight');
        }, 1000);
    }

    async saveStudent(event) {
        console.log('Начинаю сохранение изменений ученика...');

        const studentId = document.getElementById('studentId').value;

        console.log('Student ID:', studentId);

        if (!studentId || studentId === 'new') {
            alert('Для сохранения сначала выберите существующего ученика или создайте нового через кнопку "Создать нового ученика"');
            return;
        }

        // Проверяем обязательные поля
        const name = document.getElementById('name').value;
        if (!name || name.trim() === '') {
            this.showMessage('ФИО ученика обязательно для заполнения', 'danger');
            document.getElementById('name').classList.add('highlight-red');
            setTimeout(() => {
                document.getElementById('name').classList.remove('highlight-red');
            }, 1000);
            return;
        }

        // Собираем данные формы
        const formData = new FormData();

        // Добавляем все поля формы
        const fields = ['name', 'birthday', 'sport_discipline', 'rang', 'sports_rank',
                       'sex', 'weight', 'telephone', 'head_trainer_id', 'second_trainer_id',
                       'price', 'payment_day', 'classes_remaining', 'expected_payment_date',
                       'parent1', 'parent2', 'date_start', 'telegram_id', 'active'];

        fields.forEach(fieldName => {
            const element = document.getElementById(fieldName);
            if (element) {
                if (element.type === 'checkbox') {
                    formData.append(fieldName, element.checked ? 'on' : '');
                } else {
                    formData.append(fieldName, element.value || '');
                }
            }
        });

        // Добавляем student_id
        formData.append('student_id', studentId);

        // Показываем индикатор загрузки
        const submitBtn = this.form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Сохранение...';
        submitBtn.disabled = true;

        try {
            const url = `/edit-students/update-student`;

            console.log('Отправляю POST запрос на:', url);
            console.log('Данные для отправки:');
            for (let [key, value] of formData.entries()) {
                console.log(`${key}: ${value}`);
            }

            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });

            console.log('Статус ответа:', response.status);
            console.log('Статус текста:', response.statusText);

            if (!response.ok) {
                let errorDetail = `Ошибка ${response.status}`;
                try {
                    const errorData = await response.json();
                    console.log('Ошибка от сервера:', errorData);
                    errorDetail = errorData.detail || errorData.message || errorDetail;
                } catch (e) {
                    const text = await response.text();
                    console.log('Текст ошибки:', text);
                    errorDetail = text || errorDetail;
                }
                throw new Error(errorDetail);
            }

            const result = await response.json();
            console.log('✅ Успешный ответ:', result);

            // Показываем сообщение об успехе
            this.showMessage('success', result.message || 'Данные ученика успешно сохранены в базе данных');

            // Обновляем имя в выпадающем списке
            const studentSelect = document.getElementById('studentSelect');
            const currentStudentName = document.getElementById('name').value;
            if (studentSelect) {
                const option = studentSelect.querySelector(`option[value="${studentId}"]`);
                if (option) {
                    option.textContent = currentStudentName;
                }
            }

            // Подсвечиваем кнопку как успешную
            submitBtn.classList.add('btn-success');
            submitBtn.classList.remove('btn-primary');
            setTimeout(() => {
                submitBtn.classList.remove('btn-success');
                submitBtn.classList.add('btn-primary');
            }, 2000);

        } catch (error) {
            console.error('❌ Ошибка сохранения:', error);
            this.showMessage('danger', `Ошибка сохранения: ${error.message}`);
            alert('Ошибка: ' + error.message);

            // Подсвечиваем кнопку как ошибку
            submitBtn.classList.add('btn-danger');
            submitBtn.classList.remove('btn-primary');
            setTimeout(() => {
                submitBtn.classList.remove('btn-danger');
                submitBtn.classList.add('btn-primary');
            }, 2000);
        } finally {
            // Восстанавливаем кнопку
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    }

    showMessage(type, text) {
        console.log(`Показываю сообщение [${type}]:`, text);

        if (!this.messageContainer) {
            console.warn('Контейнер для сообщений не найден');
            return;
        }

        this.messageContainer.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
                ${text}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;


        // Автоматически скрыть через 5 секунд
        setTimeout(() => {
            const alert = this.messageContainer.querySelector('.alert');
            if (alert) {
                alert.remove();
            }
        }, 5000);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM загружен, инициализирую StudentFormManager');
    window.studentFormManager = new StudentFormManager();
});