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
    }

    setupEventListeners() {
        // Кнопка открытия модального окна
        document.addEventListener('click', (e) => {
            if (e.target.id === 'openPaymentModal' || e.target.closest('#openPaymentModal')) {
                this.openPaymentModal();
            }
        });

        // Подтверждение оплаты
        document.addEventListener('click', (e) => {
            if (e.target.id === 'confirmPayment' || e.target.closest('#confirmPayment')) {
                this.processPayment();
            }
        });

        // Изменение суммы
        const amountInput = document.getElementById('amount');
        if (amountInput) {
            amountInput.addEventListener('input', (e) => {
                this.updatePreview(e.target.value);
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
        document.getElementById('currentBalance').value = this.currentBalance;
        document.getElementById('amount').value = '';
        document.getElementById('confirmPayment').disabled = true;

        // Обновляем информацию об ученике
        this.updateStudentInfo();

        // Загружаем доступные тарифы
        this.loadPrices();

        // Сбрасываем предпросмотр
        document.getElementById('paymentPreview').classList.add('d-none');

        // Показываем модальное окно
        const modal = new bootstrap.Modal(document.getElementById('paymentModal'));
        modal.show();
    }

    updateStudentInfo() {
        const infoDiv = document.getElementById('studentPaymentInfo');
        const currentDate = new Date().toLocaleDateString('ru-RU');
        const nextPayment = document.getElementById('expected_payment_date').value;

        let nextPaymentText = 'не установлена';
        if (nextPayment) {
            const date = new Date(nextPayment);
            nextPaymentText = date.toLocaleDateString('ru-RU');
        }

        infoDiv.innerHTML = `
            <div class="text-start">
                <p class="mb-1"><strong>${this.currentStudentName}</strong></p>
                <p class="mb-1 small">Текущий баланс: <span class="badge ${this.currentBalance > 5 ? 'bg-success' : this.currentBalance > 0 ? 'bg-warning' : 'bg-danger'}">
                    ${this.currentBalance} занятий
                </span></p>
                <p class="mb-0 small">След. оплата: ${nextPaymentText}</p>
                <p class="mb-0 small text-muted">Сегодня: ${currentDate}</p>
            </div>
        `;
    }

    async loadPrices() {
        try {
            // Получаем список тарифов из скрытого поля или API
            const priceSelect = document.getElementById('price');
            if (priceSelect && priceSelect.options) {
                this.availablePrices = [];
                for (let option of priceSelect.options) {
                    if (option.value) {
                        this.availablePrices.push({
                            id: option.value,
                            price: option.getAttribute('data-price-amount'),
                            classes_in_price: option.getAttribute('data-classes-count') || 0,
                            description: option.text.split(' - ')[0]
                        });
                    }
                }
                this.renderPrices();
            }
        } catch (error) {
            console.error('Error loading prices:', error);
            this.showAlert('Ошибка загрузки тарифов', 'danger');
        }
    }

    renderPrices() {
        const container = document.getElementById('availablePrices');
        if (!container) return;

        if (!this.availablePrices.length) {
            container.innerHTML = '<div class="col-12 text-center text-muted">Нет доступных тарифов</div>';
            return;
        }

        // Сортируем по цене
        this.availablePrices.sort((a, b) => a.price - b.price);

        const html = this.availablePrices.map(price => `
            <div class="col-md-6">
                <div class="card price-item border-light h-100"
                     data-price="${price.price}"
                     data-id="${price.id}"
                     style="cursor: pointer; transition: all 0.3s;"
                     onclick="window.paymentManager.selectPrice(this)">
                    <div class="card-body text-center p-3">
                        <h5 class="card-title text-primary mb-1">${price.price} ₽</h5>
                        <p class="card-text mb-1"><small>${price.description || 'Тариф'}</small></p>
                        <p class="card-text mb-0">
                            <span class="badge bg-light text-dark">
                                <i class="fas fa-dumbbell me-1"></i>
                                ${price.classes_in_price || 0} занятий
                            </span>
                        </p>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = html;
    }

    selectPrice(element) {
        // Сбрасываем выделение у всех тарифов
        document.querySelectorAll('.price-item').forEach(item => {
            item.classList.remove('selected');
            item.style.borderColor = '';
            item.style.backgroundColor = '';
        });

        // Выделяем выбранный тариф
        element.classList.add('selected');
        element.style.borderColor = '#3CB371';
        element.style.borderWidth = '2px';
        element.style.backgroundColor = 'rgba(60, 179, 113, 0.05)';

        // Устанавливаем сумму
        const price = element.dataset.price;
        document.getElementById('amount').value = price;

        this.updatePreview(price);
        this.updateConfirmButton();
    }

    updatePreview(amount) {
        if (!amount || amount <= 0) {
            document.getElementById('paymentPreview').classList.add('d-none');
            return;
        }

        // Находим соответствующий тариф
        const price = this.availablePrices.find(p => p.price == amount);
        let previewText = '';

        if (price) {
            const newBalance = this.currentBalance + (parseInt(price.classes_in_price) || 0);
            const today = new Date();
            const nextDate = new Date(today);
            nextDate.setDate(today.getDate() + 30); // +30 дней для примера
            const nextPaymentDate = nextDate.toLocaleDateString('ru-RU');

            previewText = `
                <div class="text-start">
                    <div class="row align-items-center mb-2">
                        <div class="col-6">
                            <h6 class="mb-0">${price.description || 'Тариф'}</h6>
                        </div>
                        <div class="col-6 text-end">
                            <span class="badge bg-primary">${price.price} ₽</span>
                        </div>
                    </div>
                    <hr class="my-2">
                    <div class="row">
                        <div class="col-6">
                            <div class="mb-2">
                                <small class="text-muted">Текущий баланс:</small><br>
                                <span class="badge bg-secondary">${this.currentBalance} занятий</span>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="mb-2">
                                <small class="text-muted">Добавляется:</small><br>
                                <span class="badge bg-success">+${price.classes_in_price || 0} занятий</span>
                            </div>
                        </div>
                    </div>
                    <hr class="my-2">
                    <div class="text-center">
                        <p class="mb-1"><small class="text-muted">Новый баланс:</small></p>
                        <h4 class="text-success mb-1">${newBalance} занятий</h4>
                        <p class="mb-0 small text-muted">Следующая оплата: ≈ ${nextPaymentDate}</p>
                    </div>
                </div>
            `;
        } else {
            previewText = `
                <div class="text-center">
                    <div class="alert alert-warning mb-0">
                        <i class="fas fa-exclamation-triangle me-1"></i>
                        Сумма ${amount} ₽ не соответствует ни одному тарифу
                        <div class="mt-1 small">Занятия будут добавлены вручную</div>
                    </div>
                </div>
            `;
        }

        document.getElementById('previewText').innerHTML = previewText;
        document.getElementById('paymentPreview').classList.remove('d-none');
    }

    updateConfirmButton() {
        const amount = document.getElementById('amount').value;
        const confirmBtn = document.getElementById('confirmPayment');
        confirmBtn.disabled = !amount || amount <= 0;
    }

    async processPayment() {
        const amount = document.getElementById('amount').value;
        const studentId = this.currentStudentId;

        if (!amount || amount <= 0) {
            this.showAlert('Введите корректную сумму', 'danger');
            return;
        }

        const confirmBtn = document.getElementById('confirmPayment');
        const originalText = confirmBtn.innerHTML;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Обработка...';
        confirmBtn.disabled = true;

        try {
            const response = await fetch(`/api/student/${studentId}/process-payment`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ amount: parseInt(amount) })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка сервера');
            }

            const result = await response.json();

            if (result.success) {
                // Обновляем данные на странице
                this.updateStudentData(result);

                // Показываем сообщение об успехе
                this.showAlert(result.message, 'success');

                // Закрываем модальное окно через 2 секунды
                setTimeout(() => {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('paymentModal'));
                    modal.hide();

                    // Показываем уведомление
                    this.showSuccessToast(result);
                }, 2000);
            } else {
                throw new Error(result.error || 'Ошибка при обработке оплаты');
            }
        } catch (error) {
            this.showAlert(error.message, 'danger');
        } finally {
            confirmBtn.innerHTML = '<i class="fas fa-check me-1"></i> Подтвердить оплату';
            this.updateConfirmButton();
        }
    }

    updateStudentData(paymentResult) {
        // Обновляем остаток занятий
        const balanceInput = document.getElementById('classes_remaining');
        if (balanceInput) {
            balanceInput.value = paymentResult.new_balance;

            // Анимация
            balanceInput.classList.add('highlight');
            setTimeout(() => balanceInput.classList.remove('highlight'), 1000);

            // Обновляем статус
            this.updateBalanceStatus(paymentResult.new_balance);
        }

        // Обновляем тариф если нужно
        const priceSelect = document.getElementById('price');
        if (priceSelect) {
            // Можно обновить выбранный тариф на основе paymentResult.price_description
        }

        // Обновляем дату следующей оплаты
        const dateInput = document.getElementById('expected_payment_date');
        if (dateInput && paymentResult.next_payment_date) {
            const [day, month, year] = paymentResult.next_payment_date.split('.');
            dateInput.value = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;

            // Обновляем статус даты
            this.updateDateStatus(dateInput.value);
        }
    }

    updateBalanceStatus(balance) {
        const statusDiv = document.getElementById('balanceStatus');
        const icon = document.getElementById('balanceIcon');

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

    updateDateStatus(dateString) {
        const statusDiv = document.getElementById('dateStatus');
        const icon = document.getElementById('dateIcon');

        if (!dateString) {
            statusDiv.innerHTML = '<span class="text-muted">Дата не установлена</span>';
            icon.className = 'fas fa-clock text-muted';
            return;
        }

        const date = new Date(dateString);
        const today = new Date();
        const diffDays = Math.ceil((date - today) / (1000 * 60 * 60 * 24));

        if (diffDays > 14) {
            statusDiv.innerHTML = `<span class="text-success">Оплата через ${diffDays} дней</span>`;
            icon.className = 'fas fa-calendar-check text-success';
        } else if (diffDays > 7) {
            statusDiv.innerHTML = `<span class="text-warning">Оплата через ${diffDays} дней</span>`;
            icon.className = 'fas fa-clock text-warning';
        } else if (diffDays > 0) {
            statusDiv.innerHTML = `<span class="text-danger">Оплата через ${diffDays} дней</span>`;
            icon.className = 'fas fa-exclamation-triangle text-danger';
        } else if (diffDays === 0) {
            statusDiv.innerHTML = '<span class="text-danger">Оплата сегодня!</span>';
            icon.className = 'fas fa-exclamation-circle text-danger';
        } else {
            statusDiv.innerHTML = `<span class="text-danger">Просрочена на ${Math.abs(diffDays)} дней</span>`;
            icon.className = 'fas fa-calendar-times text-danger';
        }
    }

    showAlert(message, type = 'danger') {
        const alertDiv = document.getElementById('paymentAlert');
        alertDiv.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        alertDiv.classList.remove('d-none');
    }


    showSuccessToast(result) {
        // Создаем контейнер для тостов если его нет
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }

        const toastId = 'payment-toast-' + Date.now();
        const toastHTML = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header bg-success text-white">
                    <strong class="me-auto">
                        <i class="fas fa-check-circle me-2"></i>
                        Оплата успешна
                    </strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    <div class="mb-2">
                        <strong>${result.student_name}</strong>
                    </div>
                    <div class="row small">
                        <div class="col-6">Сумма:</div>
                        <div class="col-6 text-end"><strong>${result.amount} ₽</strong></div>
                    </div>
                    <div class="row small">
                        <div class="col-6">Добавлено:</div>
                        <div class="col-6 text-end"><span class="badge bg-success">+${result.classes_added} занятий</span></div>
                    </div>
                    <div class="row small">
                        <div class="col-6">Новый баланс:</div>
                        <div class="col-6 text-end"><strong>${result.new_balance} занятий</strong></div>
                    </div>
                    <hr class="my-1">
                    <div class="text-center small text-muted">
                        Следующая оплата: ${result.next_payment_date}
                    </div>
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHTML);

        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, {
            delay: 5000
        });
        toast.show();

        // Удаляем тост после скрытия
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.paymentManager = new PaymentManager();
});