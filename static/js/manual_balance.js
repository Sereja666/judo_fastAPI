// static/js/manual_balance.js - упрощенная версия без быстрых кнопок
document.addEventListener('DOMContentLoaded', function() {
    console.log('ManualBalanceManager loaded');

    // Кнопка открытия модального окна
    const openBtn = document.getElementById('manualBalanceEdit');
    if (openBtn) {
        openBtn.addEventListener('click', openManualBalanceModal);
    }

    // Сохранение изменений
    const saveBtn = document.getElementById('saveManualBalance');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveManualBalance);
    }

    // Обновление предпросмотра при изменении значения
    const newBalanceInput = document.getElementById('newBalance');
    if (newBalanceInput) {
        newBalanceInput.addEventListener('input', updateBalancePreview);
    }
});

let currentStudentData = {
    id: null,
    name: '',
    balance: 0
};

function openManualBalanceModal() {
    const studentId = document.getElementById('studentId')?.value;
    if (!studentId) {
        alert('Сначала выберите ученика');
        return;
    }

    currentStudentData = {
        id: studentId,
        name: document.getElementById('name')?.value || '',
        balance: parseInt(document.getElementById('classes_remaining')?.value) || 0
    };

    // Заполняем форму
    const manualBalanceStudentId = document.getElementById('manualBalanceStudentId');
    const currentBalanceValue = document.getElementById('currentBalanceValue');
    const newBalanceInput = document.getElementById('newBalance');

    if (manualBalanceStudentId) manualBalanceStudentId.value = studentId;
    if (currentBalanceValue) currentBalanceValue.value = currentStudentData.balance;
    if (newBalanceInput) {
        newBalanceInput.value = currentStudentData.balance;
        newBalanceInput.focus();
        newBalanceInput.select();
    }

    // Очищаем причину
    const reasonInput = document.getElementById('balanceReason');
    if (reasonInput) reasonInput.value = '';

    // Очищаем алерт
    const alertDiv = document.getElementById('manualBalanceAlert');
    if (alertDiv) {
        alertDiv.classList.add('d-none');
        alertDiv.innerHTML = '';
    }

    // Обновляем информацию об ученике
    updateStudentBalanceInfo();

    // Обновляем предпросмотр
    updateBalancePreview();

    // Показываем модальное окно
    const modalElement = document.getElementById('manualBalanceModal');
    if (modalElement) {
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }
}

function updateStudentBalanceInfo() {
    const infoDiv = document.getElementById('studentBalanceInfo');
    if (!infoDiv) return;

    infoDiv.innerHTML = `
        <div class="text-center">
            <h6 class="mb-2">${currentStudentData.name}</h6>
            <div class="mb-2">
                <span class="badge ${currentStudentData.balance > 10 ? 'bg-success' : currentStudentData.balance > 5 ? 'bg-warning' : 'bg-danger'} p-2">
                    <i class="fas fa-dumbbell me-1"></i>
                    Текущий баланс: <strong>${currentStudentData.balance} занятий</strong>
                </span>
            </div>
        </div>
    `;
}

function updateBalancePreview() {
    const newBalanceInput = document.getElementById('newBalance');
    const previewElement = document.getElementById('balancePreview');
    const previewTextElement = document.getElementById('balancePreviewText');

    if (!newBalanceInput || !previewElement || !previewTextElement) return;

    const newBalance = parseInt(newBalanceInput.value) || 0;

    if (newBalance === currentStudentData.balance) {
        previewElement.classList.add('d-none');
        return;
    }

    const difference = newBalance - currentStudentData.balance;

    const previewText = `
        <div class="text-center">
            <div class="mb-3">
                <span class="badge bg-secondary fs-6">${currentStudentData.balance}</span>
                <i class="fas fa-arrow-right mx-3 text-muted fs-5"></i>
                <span class="badge ${newBalance > 10 ? 'bg-success' : newBalance > 5 ? 'bg-warning' : 'bg-danger'} fs-6">
                    ${newBalance}
                </span>
            </div>
            <div>
                <span class="badge ${difference > 0 ? 'bg-success' : 'bg-danger'} fs-6">
                    ${difference > 0 ? '+' : ''}${difference} занятий
                </span>
                <p class="mt-2 mb-0 small text-muted">
                    ${difference > 0 ? 'Баланс будет увеличен' : 'Баланс будет уменьшен'}
                </p>
            </div>
        </div>
    `;

    previewTextElement.innerHTML = previewText;
    previewElement.classList.remove('d-none');
}

async function saveManualBalance() {
    const newBalanceInput = document.getElementById('newBalance');
    const reasonInput = document.getElementById('balanceReason');

    if (!newBalanceInput || !currentStudentData.id) {
        showBalanceAlert('Ошибка: данные не загружены', 'danger');
        return;
    }

    const newBalance = newBalanceInput.value;
    const reason = reasonInput?.value || 'Ручная корректировка';

    // Валидация
    if (!newBalance || newBalance === '') {
        showBalanceAlert('Введите значение баланса', 'warning');
        newBalanceInput.focus();
        return;
    }

    if (newBalance < 0) {
        showBalanceAlert('Баланс не может быть отрицательным', 'warning');
        newBalanceInput.focus();
        return;
    }

    const saveBtn = document.getElementById('saveManualBalance');
    if (!saveBtn) return;

    // Блокируем кнопку
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Сохранение...';
    saveBtn.disabled = true;

    try {
        const response = await fetch(`/api/student/${currentStudentData.id}/update-balance`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                new_balance: parseInt(newBalance),
                reason: reason
            })
        });

        // Проверяем статус ответа
        if (!response.ok) {
            let errorMessage = `Ошибка ${response.status}`;

            // Пробуем получить JSON с ошибкой
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorData.detail || errorMessage;
            } catch (e) {
                // Не JSON ответ
                const text = await response.text();
                if (text) {
                    errorMessage = text.substring(0, 100);
                }
            }

            throw new Error(errorMessage);
        }

        // Получаем успешный ответ
        const result = await response.json();

        if (result.success) {
            // Успех! Обновляем интерфейс

            // 1. Обновляем поле на основной странице
            const mainBalanceInput = document.getElementById('classes_remaining');
            if (mainBalanceInput) {
                mainBalanceInput.value = result.new_balance;

                // Анимация
                mainBalanceInput.classList.add('highlight');
                setTimeout(() => mainBalanceInput.classList.remove('highlight'), 1000);
            }

            // 2. Обновляем текущие данные
            currentStudentData.balance = result.new_balance;

            // 3. Показываем сообщение об успехе
            showBalanceAlert(result.message, 'success');

            // 4. Закрываем модальное окно через 2 секунды
            setTimeout(() => {
                const modalElement = document.getElementById('manualBalanceModal');
                if (modalElement) {
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) {
                        modal.hide();
                    }
                }

                // 5. Показываем уведомление
                showBalanceSuccessToast(result);

                // 6. Обновляем статус на основной странице если есть PaymentManager
                if (window.paymentManager && window.paymentManager.updateBalanceStatus) {
                    window.paymentManager.updateBalanceStatus(result.new_balance);
                }

            }, 2000);

        } else {
            throw new Error(result.error || 'Неизвестная ошибка');
        }

    } catch (error) {
        console.error('Balance update error:', error);
        showBalanceAlert(`Ошибка сохранения: ${error.message}`, 'danger');
    } finally {
        // Восстанавливаем кнопку
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    }
}

function showBalanceAlert(message, type = 'danger') {
    const alertDiv = document.getElementById('manualBalanceAlert');
    if (!alertDiv) return;

    alertDiv.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    alertDiv.classList.remove('d-none');

    // Автоскрытие успешных сообщений
    if (type === 'success') {
        setTimeout(() => {
            if (alertDiv) {
                alertDiv.classList.add('d-none');
            }
        }, 5000);
    }
}

function showBalanceSuccessToast(result) {
    // Создаем контейнер для тостов если его нет
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }

    const difference = result.difference || (result.new_balance - result.old_balance);
    const toastId = 'balance-toast-' + Date.now();

    const toastHTML = `
        <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header bg-success text-white">
                <strong class="me-auto">
                    <i class="fas fa-check-circle me-2"></i>
                    Баланс сохранен
                </strong>
                <small>только что</small>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                <div class="mb-2">
                    <strong>${result.student_name}</strong>
                </div>
                <div class="row small align-items-center mb-1">
                    <div class="col-4 text-end">
                        <span class="badge bg-secondary">${result.old_balance}</span>
                    </div>
                    <div class="col-4 text-center">
                        <i class="fas fa-arrow-right text-muted"></i>
                    </div>
                    <div class="col-4">
                        <span class="badge ${result.new_balance > 10 ? 'bg-success' : result.new_balance > 5 ? 'bg-warning' : 'bg-danger'}">
                            ${result.new_balance}
                        </span>
                    </div>
                </div>
                <div class="text-center mb-1">
                    <span class="badge ${difference > 0 ? 'bg-success' : 'bg-danger'}">
                        ${difference > 0 ? '+' : ''}${difference}
                    </span>
                </div>
                ${result.reason ? `
                <div class="mt-2 pt-2 border-top small">
                    <i class="fas fa-sticky-note me-1 text-muted"></i>
                    <span class="text-muted">Причина:</span> ${result.reason}
                </div>
                ` : ''}
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML('beforeend', toastHTML);

    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        delay: 6000
    });
    toast.show();

    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

// Добавьте в manual_balance.js
document.getElementById('viewBalanceHistory')?.addEventListener('click', async function() {
    const studentId = document.getElementById('studentId')?.value;
    if (!studentId) {
        alert('Сначала выберите ученика');
        return;
    }

    try {
        const response = await fetch(`/api/student/${studentId}/balance-history`);
        const result = await response.json();

        if (result.success) {
            showBalanceHistoryModal(result.history);
        } else {
            alert('Ошибка загрузки истории: ' + result.error);
        }
    } catch (error) {
        console.error('Error loading history:', error);
        alert('Ошибка загрузки истории');
    }
});

function showBalanceHistoryModal(history) {
    if (!history || history.length === 0) {
        alert('История изменений отсутствует');
        return;
    }

    let historyHTML = '<div class="table-responsive"><table class="table table-sm">';
    historyHTML += `
        <thead>
            <tr>
                <th>Дата</th>
                <th>Старый баланс</th>
                <th>Новый баланс</th>
                <th>Изменение</th>
                <th>Причина</th>
            </tr>
        </thead>
        <tbody>
    `;

    history.forEach(log => {
        historyHTML += `
            <tr>
                <td>${log.changed_at}</td>
                <td><span class="badge bg-secondary">${log.old_balance}</span></td>
                <td><span class="badge ${log.new_balance > log.old_balance ? 'bg-success' : 'bg-danger'}">${log.new_balance}</span></td>
                <td><span class="badge ${log.difference > 0 ? 'bg-success' : 'bg-danger'}">${log.difference > 0 ? '+' : ''}${log.difference}</span></td>
                <td><small>${log.reason}</small></td>
            </tr>
        `;
    });

    historyHTML += '</tbody></table></div>';

    // Показываем в модальном окне
    const modalHTML = `
        <div class="modal fade" id="historyModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header bg-info text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-history me-2"></i>
                            История изменений баланса
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        ${historyHTML}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
                    </div>
                </div>
            </div>
        </div>
    `;


    // Удаляем старую модалку если есть
    const oldModal = document.getElementById('historyModal');
    if (oldModal) oldModal.remove();

    // Добавляем новую
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Показываем
    const modal = new bootstrap.Modal(document.getElementById('historyModal'));
    modal.show();
}