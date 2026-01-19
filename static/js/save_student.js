// static/js/save_student.js
async function saveStudentChanges() {
    console.log('🎯 Кнопка "Сохранить изменения" нажата!');

    const studentId = document.getElementById('studentId').value;

    if (!studentId || studentId === 'new') {
        alert('Сначала выберите существующего ученика или создайте нового');
        return;
    }

    // Показываем индикатор загрузки
    const button = document.querySelector('button[onclick="saveStudentChanges()"]');
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Сохранение...';
    button.disabled = true;

    try {
        // Собираем данные из формы
        const formData = new FormData();

        // Список всех полей из формы
        const fields = [
            'name', 'birthday', 'sport_discipline', 'rang', 'sports_rank',
            'sex', 'weight', 'telephone', 'head_trainer_id', 'second_trainer_id',
            'price', 'payment_day', 'classes_remaining', 'expected_payment_date',
            'parent1', 'parent2', 'date_start', 'telegram_id'
        ];

        // Добавляем каждое поле
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

        // Добавляем поле active
        const activeElement = document.getElementById('active');
        if (activeElement) {
            formData.append('active', activeElement.checked ? 'on' : '');
        }

        // Добавляем student_id
        formData.append('student_id', studentId);

        console.log('📤 Отправляю данные ученика:', Object.fromEntries(formData.entries()));

        // Отправляем запрос
        const response = await fetch('/edit-students/update-student', {
            method: 'POST',
            body: formData
        });

        console.log('📥 Ответ сервера:', response.status);

        if (response.ok) {
            const result = await response.json();
            console.log('✅ Данные сохранены:', result);

            // Показываем сообщение об успехе
            showStudentMessage(result.message || 'Данные успешно сохранены', 'success');

            // Обновляем имя в выпадающем списке
            const studentName = document.getElementById('name').value;
            const studentSelect = document.getElementById('studentSelect');
            if (studentSelect) {
                const option = studentSelect.querySelector(`option[value="${studentId}"]`);
                if (option) {
                    option.textContent = studentName;
                }
            }

            // Подсвечиваем кнопку
            button.classList.add('btn-success');
            button.classList.remove('btn-primary');
            setTimeout(() => {
                button.classList.remove('btn-success');
                button.classList.add('btn-primary');
            }, 2000);

        } else {
            const errorText = await response.text();
            console.error('❌ Ошибка сервера:', errorText);
            showStudentMessage(`Ошибка сохранения: ${response.status}`, 'danger');

            button.classList.add('btn-danger');
            button.classList.remove('btn-primary');
            setTimeout(() => {
                button.classList.remove('btn-danger');
                button.classList.add('btn-primary');
            }, 2000);
        }

    } catch (error) {
        console.error('❌ Ошибка:', error);
        showStudentMessage('Ошибка соединения: ' + error.message, 'danger');
    } finally {
        // Восстанавливаем кнопку
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

function showStudentMessage(text, type) {
    const container = document.getElementById('message');
    if (!container) {
        console.warn('Контейнер для сообщений не найден');
        return;
    }

    container.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
            ${text}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    // Автоматически скрыть через 5 секунд
    setTimeout(() => {
        const alert = container.querySelector('.alert');
        if (alert) {
            alert.remove();
        }
    }, 5000);
}
function resetForm() {
    if (confirm('Вы уверены, что хотите сбросить все изменения?')) {
        const form = document.getElementById('studentForm');
        if (form) {
            form.reset();
            showStudentMessage('Форма сброшена', 'info');
        }
    }
}
// Добавьте в конец save_student.js
function openPaymentModal() {
    const studentId = document.getElementById('studentId').value;
    if (!studentId || studentId === 'new') {
        alert('Сначала выберите или создайте ученика');
        return;
    }
    // Здесь код для открытия модального окна оплаты
    console.log('Открытие модального окна оплаты для ученика', studentId);
}

function openMedicalCertificateModal() {
    const studentId = document.getElementById('studentId').value;
    if (!studentId || studentId === 'new') {
        alert('Сначала выберите или создайте ученика');
        return;
    }
    // Здесь код для открытия модального окна справок
    console.log('Открытие модального окна справок для ученика', studentId);
}

function openManualBalanceModal() {
    const studentId = document.getElementById('studentId').value;
    if (!studentId || studentId === 'new') {
        alert('Сначала выберите или создайте ученика');
        return;
    }
    // Здесь код для открытия модального окна ручного баланса
    console.log('Открытие модального окна ручного баланса для ученика', studentId);
}
// Экспортируем для глобального доступа
window.saveStudentChanges = saveStudentChanges;
window.showStudentMessage = showStudentMessage;