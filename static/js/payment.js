// static/js/payment.js
class PaymentManager {
    constructor() {
        this.currentStudentId = null;
        this.currentStudentName = null;
        this.currentBalance = 0;
        this.availablePrices = [];
        this.initialize();
    }

    initialize() {
        this.setupEventListeners();
        this.setupBalanceSaveListener();
    }

    setupBalanceSaveListener() {
        // Кнопка сохранения баланса
        const saveBalanceBtn = document.getElementById('saveBalanceBtn');
        if (saveBalanceBtn) {
            saveBalanceBtn.addEventListener('click', () => this.saveCurrentBalance());
        }

        // Автосохранение при потере фокуса (опционально)
        const balanceInput = document.getElementById('classes_remaining');
        if (balanceInput) {
            balanceInput.addEventListener('blur', (e) => {
                const newValue = parseInt(e.target.value) || 0;
                const oldValue = this.currentBalance;

                // Сохраняем если значение изменилось
                if (newValue !== oldValue && Math.abs(newValue - oldValue) > 0) {
                    setTimeout(() => this.saveCurrentBalance(), 500);
                }
            });
        }
    }

    async saveCurrentBalance() {
        const balanceInput = document.getElementById('classes_remaining');
        const studentId = document.getElementById('studentId')?.value;
        const saveBtn = document.getElementById('saveBalanceBtn');

        if (!studentId) {
            this.showBalanceStatus('Сначала выберите ученика', 'danger');
            return;
        }

        const newBalance = parseInt(balanceInput.value) || 0;

        if (newBalance < 0) {
            this.showBalanceStatus('Баланс не может быть отрицательным', 'danger');
            return;
        }

        // Запоминаем старое значение для отката
        const oldBalance = this.currentBalance;

        // Визуальная обратная связь
        if (saveBtn) {
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            saveBtn.disabled = true;
            saveBtn.classList.remove('btn-success');
            saveBtn.classList.add('btn-warning');
        }

        this.showBalanceStatus('Сохранение...', 'info');

        try {
            const response = await fetch(`/api/student/${studentId}/update-balance`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    new_balance: newBalance,
                    reason: 'Ручное изменение в интерфейсе'
                })
            });

            // Проверяем, что ответ JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Non-JSON response:', text.substring(0, 200));

                // Пробуем разобрать как текст
                if (text.includes('Internal Server Error')) {
                    throw new Error('Внутренняя ошибка сервера');
                } else if (text.includes('CSRF')) {
                    throw new Error('Ошибка безопасности. Обновите страницу.');
                } else {
                    throw new Error('Сервер вернул некорректный ответ');
                }
            }

            const result = await response.json();

            if (!response.ok) {
                // Если endpoint вернул ошибку в JSON
                throw new Error(result.error || result.detail || `Ошибка ${response.status}`);
            }

            if (result.success) {
                // Успешно сохранено
                this.currentBalance = newBalance;

                // Обновляем статус
                this.updateBalanceStatus(newBalance);
                this.showBalanceStatus(result.message, 'success');

                // Анимация успеха
                if (saveBtn) {
                    saveBtn.innerHTML = '<i class="fas fa-check"></i>';
                    saveBtn.classList.remove('btn-warning');
                    saveBtn.classList.add('btn-success');

                    // Возвращаем обычный вид через 2 секунды
                    setTimeout(() => {
                        if (saveBtn) {
                            saveBtn.innerHTML = '<i class="fas fa-save"></i>';
                            saveBtn.disabled = false;
                        }
                    }, 2000);
                }

                // Показываем тост
                this.showBalanceChangeToast(result);

            } else {
                throw new Error(result.error || 'Неизвестная ошибка');
            }

        } catch (error) {
            console.error('Save balance error:', error);

            // Восстанавливаем старое значение
            balanceInput.value = oldBalance;

            // Показываем ошибку
            this.showBalanceStatus(`Ошибка: ${error.message}`, 'danger');

            // Восстанавливаем кнопку
            if (saveBtn) {
                saveBtn.innerHTML = '<i class="fas fa-save"></i>';
                saveBtn.disabled = false;
                saveBtn.classList.remove('btn-warning');
                saveBtn.classList.add('btn-success');
            }
        }
    }

    showBalanceStatus(message, type = 'info') {
        const statusDiv = document.getElementById('balanceSaveStatus');
        if (!statusDiv) return;

        const colors = {
            'success': 'text-success',
            'danger': 'text-danger',
            'warning': 'text-warning',
            'info': 'text-info'
        };

        statusDiv.className = `small ${colors[type] || 'text-muted'}`;
        statusDiv.innerHTML = `<i class="fas fa-info-circle me-1"></i>${message}`;

        // Автоматически скрываем через 5 секунд если не ошибка
        if (type !== 'danger') {
            setTimeout(() => {
                statusDiv.innerHTML = '';
            }, 5000);
        }
    }

    showBalanceChangeToast(result) {
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }

        const toastId = 'balance-change-toast-' + Date.now();
        const difference = result.new_balance - result.old_balance;

        const toastHTML = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header bg-success text-white">
                    <strong class="me-auto">
                        <i class="fas fa-save me-2"></i>
                        Баланс сохранен
                    </strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    <div class="mb-2">
                        <strong>${result.student_name || 'Ученик'}</strong>
                    </div>
                    <div class="row small">
                        <div class="col-6">Старое значение:</div>
                        <div class="col-6 text-end"><span class="badge bg-secondary">${result.old_balance}</span></div>
                    </div>
                    <div class="row small">
                        <div class="col-6">Новое значение:</div>
                        <div class="col-6 text-end"><strong>${result.new_balance} занятий</strong></div>
                    </div>
                    ${difference !== 0 ? `
                    <div class="row small">
                        <div class="col-6">Изменение:</div>
                        <div class="col-6 text-end">
                            <span class="badge ${difference > 0 ? 'bg-success' : 'bg-danger'}">
                                ${difference > 0 ? '+' : ''}${difference}
                            </span>
                        </div>
                    </div>
                    ` : ''}
                    ${result.payment_date_info ? `
                    <hr class="my-1">
                    <div class="text-center small text-muted">
                        ${result.payment_date_info}
                    </div>
                    ` : ''}
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHTML);

        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, {
            delay: 4000
        });
        toast.show();

        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.paymentManager = new PaymentManager();
});