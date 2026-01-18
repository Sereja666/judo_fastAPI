// static/js/student_form.js
class StudentFormManager {
    constructor() {
        this.form = document.getElementById('studentForm');
        this.messageContainer = document.getElementById('message');
        this.initialize();
    }

    initialize() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        if (this.form) {
            this.form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveStudent();
            });
        }
    }

    async saveStudent() {
        const formData = new FormData(this.form);
        const studentId = formData.get('student_id');

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

            // Используем PUT endpoint для обновления ученика
            const response = await fetch(`/api/student/${studentId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Ошибка ${response.status}`);
            }

            const result = await response.json();

            // Показываем сообщение об успехе
            this.showMessage('success', result.message || 'Данные ученика успешно сохранены');

        } catch (error) {
            console.error('Ошибка сохранения:', error);
            this.showMessage('danger', `Ошибка сохранения: ${error.message}`);
        } finally {
            // Восстанавливаем кнопку
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    }

    showMessage(type, text) {
        if (!this.messageContainer) return;

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
                bootstrap.Alert.getInstance(alert)?.close();
            }
        }, 5000);
    }
}