// static/js/payment.js - только модальное окно оплаты
class PaymentManager {
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

        // Изменение суммы
        const amountInput = document.getElementById('amount');
        if (amountInput) {
            amountInput.addEventListener('input', (e) => {
                this.updateConfirmButton();
            });
        }
    }

    openPaymentModal() {
        const studentId = document.getElementById('studentId').value;
        if (!studentId) {
            alert('Сначала выберите ученика');
            return;
        }

        this.currentStudentId = studentId;
        this.currentStudentName = document.getElementById('name').value;
        this.currentBalance = parseInt(document.getElementById('classes_remaining').value) || 0;

        document.getElementById('paymentStudentId').value = studentId;
        document.getElementById('amount').value = '';
        document.getElementById('confirmPayment').disabled = true;

        // Показываем модальное окно
        const modalElement = document.getElementById('paymentModal');
        if (modalElement) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        }
    }

    updateConfirmButton() {
        const amount = document.getElementById('amount').value;
        const confirmBtn = document.getElementById('confirmPayment');
        if (confirmBtn) {
            confirmBtn.disabled = !amount || amount <= 0;
        }
    }

    async processPayment() {
        const amount = document.getElementById('amount').value;
        const studentId = this.currentStudentId;

        if (!amount || amount <= 0) {
            alert('Введите корректную сумму');
            return;
        }

        const confirmBtn = document.getElementById('confirmPayment');
        const originalText = confirmBtn.innerHTML;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Обработка...';
        confirmBtn.disabled = true;

        try {
            // Используем существующий endpoint оплаты
            const response = await fetch(`/api/student/${studentId}/process-payment`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ amount: parseInt(amount) })
            });

            if (!response.ok) {
                throw new Error(`Ошибка ${response.status}`);
            }

            const result = await response.json();

            if (result.success) {
                // Обновляем поле баланса на странице
                const balanceInput = document.getElementById('classes_remaining');
                if (balanceInput) {
                    balanceInput.value = result.new_balance;
                }

                // Закрываем модальное окно
                const modal = bootstrap.Modal.getInstance(document.getElementById('paymentModal'));
                modal.hide();

                alert(`Оплата успешна! Добавлено ${result.classes_added} занятий. Новый баланс: ${result.new_balance}`);
            } else {
                throw new Error(result.error || 'Ошибка при обработке оплаты');
            }
        } catch (error) {
            alert('Ошибка: ' + error.message);
        } finally {
            confirmBtn.innerHTML = '<i class="fas fa-check me-1"></i> Подтвердить оплату';
            confirmBtn.disabled = false;
        }
    }
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    window.paymentManager = new PaymentManager();
});