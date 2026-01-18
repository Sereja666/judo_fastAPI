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
    }

    setupEventListeners() {
        if (this.form) {
            console.log('Добавляю обработчик submit');
            this.form.addEventListener('submit', (e) => {
                console.log('Форма отправлена!');
                e.preventDefault();
                this.saveStudent();
            });
        }
    }

    async saveStudent() {
        console.log('Начинаю сохранение...');

        const formData = new FormData(this.form);
        const studentId = formData.get('student_id');

        console.log('Student ID:', studentId);
        console.log('Все данные формы:');
        for (let [key, value] of formData.entries()) {
            console.log(`${key}: ${value}`);
        }

        if (!studentId) {
            alert('Сначала выберите ученика');
            return;
        }

        // Показываем индикатор загрузки
        const submitBtn = this.form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Сохранение...';
        submitBtn.disabled = true;

        try {
            // Преобразуем FormData в объект для JSON
            const data = {};
            formData.forEach((value, key) => {
                data[key] = value;
            });

            console.log('Отправляю данные:', data);
            console.log('URL:', `/api/student/${studentId}`);

            // Используем PUT endpoint для обновления ученика
            const response = await fetch(`/api/student/${studentId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(data)
            });

            console.log('Статус ответа:', response.status);
            console.log('Статус текста:', response.statusText);

            if (!response.ok) {
                let errorDetail = `Ошибка ${response.status}`;
                try {
                    const errorData = await response.json();
                    console.log('Ошибка от сервера:', errorData);
                    errorDetail = errorData.detail || errorDetail;
                } catch (e) {
                    const text = await response.text();
                    console.log('Текст ошибки:', text);
                    errorDetail = text || errorDetail;
                }
                throw new Error(errorDetail);
            }

            const result = await response.json();
            console.log('Успешный ответ:', result);

            // Показываем сообщение об успехе
            this.showMessage('success', result.message || 'Данные ученика успешно сохранены');

        } catch (error) {
            console.error('Ошибка сохранения:', error);
            this.showMessage('danger', `Ошибка сохранения: ${error.message}`);
            alert('Ошибка: ' + error.message);
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
                ${text}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;

        // Автоматически скрыть через 5 секунд
        setTimeout(() => {
            const alert = this.messageContainer.querySelector('.alert');
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM загружен, инициализирую StudentFormManager');
    window.studentFormManager = new StudentFormManager();
});