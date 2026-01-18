// static/js/manual_balance.js - исправленная версия
class ManualBalanceManager {
    constructor() {
        this.currentStudentId = null;
        this.currentStudentName = null;
        this.currentBalance = 0;
        this.initialize();
    }

    initialize() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Кнопка открытия модального окна
        document.addEventListener('click', (e) => {
            if (e.target.id === 'manualBalanceEdit' || e.target.closest('#manualBalanceEdit')) {
                this.openManualBalanceModal();
            }
        });

        // Сохранение изменений
        document.addEventListener('click', (e) => {
            if (e.target.id === 'saveManualBalance' || e.target.closest('#saveManualBalance')) {
                this.saveManualBalance();
            }
        });

        // Быстрые кнопки изменения
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-balance-btn')) {
                const change = parseInt(e.target.dataset.change);
                this.applyQuickChange(change);
            }
        });

        // Изменение значения баланса
        const balanceInput = document.getElementById('newBalance');
        if (balanceInput) {
            balanceInput.addEventListener('input', () => this.updateBalancePreview());
        }
    }

    openManualBalanceModal() {
        const studentId = document.getElementById('studentId').value;
        if (!studentId) {
            alert('Сначала выберите ученика');
            return;
        }

        this.currentStudentId = studentId;
        this.currentStudentName = document.getElementById('name').value;
        this.currentBalance = parseInt(document.getElementById('classes_remaining').value) || 0;

        document.getElementById('manualBalanceStudentId').value = studentId;
        document.getElementById('currentBalanceValue').value = this.currentBalance;
        document.getElementById('newBalance').value = this.currentBalance;
        document.getElementById('balanceReason').value = '';
        document.getElementById('manualBalanceAlert').classList.add('d-none');
        document.getElementById('balancePreview').classList.add('d-none');

        // Обновляем информацию об ученике
        this.updateStudentBalanceInfo();

        // Обновляем предпросмотр
        this.updateBalancePreview();

        // Показываем модальное окно
        const modalElement = document.getElementById('manualBalanceModal');
        if (modalElement) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        }
    }

    updateStudentBalanceInfo() {
        const infoDiv = document.getElementById('studentBalanceInfo');
        const nextPayment = document.getElementById('expected_payment_date').value;

        let nextPaymentText = 'не установлена';
        if (nextPayment) {
            const date = new Date(nextPayment);
            nextPaymentText = date.toLocaleDateString('ru-RU');
        }

        if (infoDiv) {
            infoDiv.innerHTML = `
                <div class="text-center">
                    <h6 class="mb-2">${this.currentStudentName}</h6>
                    <div class="mb-2">
                        <span class="badge ${this.currentBalance > 10 ? 'bg-success' : this.currentBalance > 5 ? 'bg-warning' : 'bg-danger'} p-2">
                            <i class="fas fa-dumbbell me-1"></i>
                            Текущий баланс: <strong>${this.currentBalance} занятий</strong>
                        </span>
                    </div>
                    <div class="small text-muted">
                        Следующая оплата: ${nextPaymentText}
                    </div>
                </div>
            `;
        }
    }

    applyQuickChange(change) {
        const balanceInput = document.getElementById('newBalance');
        if (!balanceInput) return;

        let currentValue = parseInt(balanceInput.value) || 0;
        let newValue = currentValue + change;

        if (newValue < 0) {
            newValue = 0;
        }

        balanceInput.value = newValue;
        this.updateBalancePreview();
    }

    updateBalancePreview() {
        const newBalanceInput = document.getElementById('newBalance');
        const newBalance = newBalanceInput ? parseInt(newBalanceInput.value) || 0 : 0;

        if (newBalance === this.currentBalance) {
            const previewElement = document.getElementById('balancePreview');
            if (previewElement) {
                previewElement.classList.add('d-none');
            }
            return;
        }

        const difference = newBalance - this.currentBalance;
        const differenceText = difference > 0 ?
            `+${difference} занятий` :
            `${difference} занятий`;

        const previewText = `
            <div class="text-start">
                <div class="row align-items-center mb-2">
                    <div class="col-6">
                        <h6 class="mb-0">Изменение баланса</h6>
                    </div>
                    <div class="col-6 text-end">
                        <span class="badge ${difference > 0 ? 'bg-success' : 'bg-danger'}">
                            ${differenceText}
                        </span>
                    </div>
                </div>
                <hr class="my-2">
                <div class="text-center">
                    <div class="mb-2">
                        <span class="badge bg-secondary">${this.currentBalance}</span>
                        <i class="fas fa-arrow-right mx-2 text-muted"></i>
                        <span class="badge ${newBalance > 10 ? 'bg-success' : newBalance > 5 ? 'bg-warning' : 'bg-danger'}">
                            ${newBalance}
                        </span>
                    </div>
                    <p class="mb-0 small text-muted">
                        ${difference > 0 ? 'Баланс будет увеличен' : 'Баланс будет уменьшен'}
                    </p>
                </div>
            </div>
        `;

        const previewElement = document.getElementById('balancePreview');
        const previewTextElement = document.getElementById('balancePreviewText');

        if (previewElement && previewTextElement) {
            previewTextElement.innerHTML = previewText;
            previewElement.classList.remove('d-none');
        }
    }

    async saveManualBalance() {
        const newBalanceInput = document.getElementById('newBalance');
        if (!newBalanceInput) return;

        const newBalance = newBalanceInput.value;
        const studentId = this.currentStudentId;
        const reason = document.getElementById('balanceReason')?.value || 'Ручная корректировка';

        if (!newBalance || newBalance < 0) {
            this.showBalanceAlert('Введите корректное значение баланса', 'warning');
            return;
        }

        const saveBtn = document.getElementById('saveManualBalance');
        if (!saveBtn) return;

        const originalText = saveBtn.innerHTML;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Сохранение...';
        saveBtn.disabled = true;

        try {
            const response = await fetch(`/api/student/${studentId}/update-balance`, {
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

            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                const text = await response.text();
                console.error("Server returned non-JSON:", text.substring(0, 200));
                throw new Error(`Сервер вернул некорректный ответ. Статус: ${response.status}`);
            }

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `Ошибка сервера: ${response.status}`);
            }

            if (result.success) {
                // Обновляем поле на основной странице
                this.updateMainBalanceField(result);

                // Обновляем дату оплаты если изменилась
                if (result.payment_date_info) {
                    // Можно обновить поле expected_payment_date
                }

                // Показываем сообщение об успехе
                this.showBalanceAlert(result.message, 'success');

                // Закрываем модальное окно через 2 секунды
                setTimeout(() => {
                    const modalElement = document.getElementById('manualBalanceModal');
                    if (modalElement) {
                        const modal = bootstrap.Modal.getInstance(modalElement);
                        if (modal) {
                            modal.hide();
                        }
                    }

                    // Показываем уведомление
                    this.showBalanceSuccessToast(result);
                }, 2000);
            } else {
                throw new Error(result.error || 'Ошибка при обновлении баланса');
            }
        } catch (error) {
            console.error('Balance update error:', error);
            this.showBalanceAlert(error.message, 'danger');
        } finally {
            saveBtn.innerHTML = '<i class="fas fa-save me-1"></i> Сохранить изменения';
            saveBtn.disabled = false;
        }
    }

    updateMainBalanceField(result) {
        // Обновляем поле на основной странице
        const balanceInput = document.getElementById('classes_remaining');
        if (balanceInput) {
            balanceInput.value = result.new_balance;

            // Анимация
            const changeType = result.new_balance > result.old_balance ? 'highlight' : 'highlight-red';
            balanceInput.classList.add(changeType);
            setTimeout(() => balanceInput.classList.remove(changeType), 1000);

            // Обновляем статус
            if (window.paymentManager && window.paymentManager.updateBalanceStatus) {
                window.paymentManager.updateBalanceStatus(result.new_balance);
            }
        }
    }

    showBalanceAlert(message, type = 'danger') {
        const alertDiv = document.getElementById('manualBalanceAlert');
        if (!alertDiv) return;

        alertDiv.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        alertDiv.classList.remove('d-none');
    }

    showBalanceSuccessToast(result) {
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }

        const toastId = 'balance-toast-' + Date.now();
        const difference = result.new_balance - result.old_balance;
        const differenceText = difference > 0 ? `+${difference}` : `${difference}`;

        const toastHTML = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header bg-warning text-white">
                    <strong class="me-auto">
                        <i class="fas fa-edit me-2"></i>
                        Баланс изменен
                    </strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    <div class="mb-2">
                        <strong>${result.student_name}</strong>
                    </div>
                    <div class="row small">
                        <div class="col-6">Старый баланс:</div>
                        <div class="col-6 text-end"><span class="badge bg-secondary">${result.old_balance}</span></div>
                    </div>
                    <div class="row small">
                        <div class="col-6">Изменение:</div>
                        <div class="col-6 text-end">
                            <span class="badge ${difference > 0 ? 'bg-success' : 'bg-danger'}">
                                ${differenceText}
                            </span>
                        </div>
                    </div>
                    <div class="row small">
                        <div class="col-6">Новый баланс:</div>
                        <div class="col-6 text-end"><strong>${result.new_balance} занятий</strong></div>
                    </div>
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
            delay: 5000
        });
        toast.show();

        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.manualBalanceManager = new ManualBalanceManager();
});