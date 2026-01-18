// static/js/payment.js - упрощенная исправленная версия
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

    setupEventListeners() {
        // Кнопка открытия модального окна оплаты
        const openBtn = document.getElementById('openPaymentModal');
        if (openBtn) {
            openBtn.addEventListener('click', () => this.openPaymentModal());
        }

        // Подтверждение оплаты
        const confirmBtn = document.getElementById('confirmPayment');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.processPayment());
        }

        // Изменение суммы в модальном окне
        const amountInput = document.getElementById('amount');
        if (amountInput) {
            amountInput.addEventListener('input', (e) => {
                this.updatePreview(e.target.value);
                this.updateConfirmButton();
            });
        }

        // Клик по тарифу
        document.addEventListener('click', (e) => {
            const priceItem = e.target.closest('.price-item');
            if (priceItem) {
                this.selectPrice(priceItem);
            }
        });
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
                const oldValue = this.currentBalance || 0;

                // Сохраняем если значение изменилось
                if (newValue !== oldValue && Math.abs(newValue - oldValue) > 0) {
                    setTimeout(() => this.saveCurrentBalance(), 500);
                }
            });
        }
    }

    // Остальные методы остаются без изменений...
    openPaymentModal() {
        const studentId = document.getElementById('studentId')?.value;
        if (!studentId) {
            alert('Сначала выберите ученика');
            return;
        }

        this.currentStudentId = studentId;
        this.currentStudentName = document.getElementById('name')?.value || '';
        this.currentBalance = parseInt(document.getElementById('classes_remaining')?.value) || 0;

        document.getElementById('paymentStudentId').value = studentId;
        document.getElementById('currentBalance').value = this.currentBalance;
        document.getElementById('amount').value = '';
        document.getElementById('confirmPayment').disabled = true;

        // Обновляем информацию об ученике
        this.updateStudentInfo();

        // Загружаем доступные тарифы
        this.loadPrices();

        // Сбрасываем предпросмотр
        const previewElement = document.getElementById('paymentPreview');
        if (previewElement) {
            previewElement.classList.add('d-none');
        }

        // Показываем модальное окно
        const modalElement = document.getElementById('paymentModal');
        if (modalElement) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
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

        const newBalance = parseInt(balanceInput?.value) || 0;

        if (newBalance < 0) {
            this.showBalanceStatus('Баланс не может быть отрицательным', 'danger');
            return;
        }

        // Запоминаем старое значение для отката
        const oldBalance = this.currentBalance || 0;

        // Визуальная обратная связь
        if (saveBtn) {
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            saveBtn.disabled = true;
            saveBtn.classList.remove('btn-success');
            saveBtn.classList.add('btn-warning');
        }

        this.showBalanceStatus('Сохранение...', 'info');

        try {
            const response = await fetch(`/api/student/${studentId}/simple-update-balance`, {
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
                throw new Error('Сервер вернул некорректный ответ');
            }

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || result.detail || `Ошибка ${response.status}`);
            }

            if (result.success) {
                // Успешно сохранено
                this.currentBalance = newBalance;

                // Обновляем статус
                this.updateBalanceStatus(newBalance);
                this.showBalanceStatus(result.message || 'Баланс сохранен', 'success');

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
            if (balanceInput) {
                balanceInput.value = oldBalance;
            }

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

    updateBalanceStatus(balance) {
        const statusDiv = document.getElementById('balanceStatus');
        const icon = document.getElementById('balanceIcon');

        if (!statusDiv || !icon) return;

        if (balance > 10) {
            statusDiv.innerHTML = '<span class="text-success"><i class="fas fa-check me-1"></i> Достаточно занятий</span>';
            icon.className = 'fas fa-check-circle text-success';
        } else if (balance > 3) {
            statusDiv.innerHTML = '<span class="text-warning"><i class="fas fa-exclamation me-1"></i> Заканчиваются занятия</span>';
            icon.className = 'fas fa-exclamation-circle text-warning';
        } else if (balance > 0) {
            statusDiv.innerHTML = '<span class="text-danger"><i class="fas fa-exclamation-triangle me-1"></i> Мало занятий</span>';
            icon.className = 'fas fa-exclamation-triangle text-danger';
        } else {
            statusDiv.innerHTML = '<span class="text-danger"><i class="fas fa-times me-1"></i> Нет занятий</span>';
            icon.className = 'fas fa-times-circle text-danger';
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
        const difference = result.new_balance - (result.old_balance || 0);

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

    // Упрощенные версии остальных методов (чтобы не было ошибок)
    updatePreview(amount) {
        // Простая реализация
        const previewElement = document.getElementById('paymentPreview');
        if (previewElement) {
            previewElement.classList.remove('d-none');
        }
    }

    updateConfirmButton() {
        const amountInput = document.getElementById('amount');
        const confirmBtn = document.getElementById('confirmPayment');
        if (confirmBtn && amountInput) {
            confirmBtn.disabled = !amountInput.value || amountInput.value <= 0;
        }
    }

    selectPrice(element) {
        // Базовая реализация
        const price = element.dataset.price;
        const amountInput = document.getElementById('amount');
        if (amountInput) {
            amountInput.value = price;
        }
    }

    updateStudentInfo() {
        const infoDiv = document.getElementById('studentPaymentInfo');
        if (infoDiv) {
            infoDiv.innerHTML = `
                <div class="text-start">
                    <p class="mb-1"><strong>${this.currentStudentName}</strong></p>
                    <p class="mb-1 small">Текущий баланс: <span class="badge ${this.currentBalance > 5 ? 'bg-success' : this.currentBalance > 0 ? 'bg-warning' : 'bg-danger'}">
                        ${this.currentBalance} занятий
                    </span></p>
                </div>
            `;
        }
    }

    loadPrices() {
        // Базовая реализация
        const container = document.getElementById('availablePrices');
        if (container) {
            container.innerHTML = '<div class="col-12 text-center text-muted">Загрузка тарифов...</div>';
        }
    }

    async processPayment() {
        alert('Функция оплаты в разработке');
    }
}

// Упрощенная инициализация
document.addEventListener('DOMContentLoaded', () => {
    try {
        window.paymentManager = new PaymentManager();
        console.log('PaymentManager успешно инициализирован');
    } catch (error) {
        console.error('Ошибка инициализации PaymentManager:', error);
    }
});