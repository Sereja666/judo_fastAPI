// static/js/medical_certificates.js
class MedicalCertificateManager {
    constructor() {
        this.currentStudentId = null;
        this.currentStudentName = null;
        this.certificates = [];
        this.initialize();
    }

    initialize() {
        this.setupEventListeners();
        this.initDatepickers();
    }

    setupEventListeners() {
        // Кнопка открытия модального окна
        document.addEventListener('click', (e) => {
            if (e.target.id === 'openMedicalCertModal' || e.target.closest('#openMedicalCertModal')) {
                this.openMedicalCertModal();
            }
        });

        // Добавление справки
        document.addEventListener('click', (e) => {
            if (e.target.id === 'addMedicalCert' || e.target.closest('#addMedicalCert')) {
                this.addMedicalCertificate();
            }
        });

        // Показать историю справок
        document.addEventListener('click', (e) => {
            if (e.target.id === 'showCertHistory' || e.target.closest('#showCertHistory')) {
                this.toggleCertHistory();
            }
        });

        // Изменение дат
        const startDateInput = document.getElementById('certStartDate');
        const endDateInput = document.getElementById('certEndDate');

        if (startDateInput) {
            startDateInput.addEventListener('change', () => this.updateCertPreview());
        }
        if (endDateInput) {
            endDateInput.addEventListener('change', () => this.updateCertPreview());
        }
    }

    initDatepickers() {
        // Инициализация datepickers (используем простые input type="date" для упрощения)
        const today = new Date().toISOString().split('T')[0];

        // Можно добавить кастомные datepickers если нужно
        // Например: flatpickr или другие библиотеки
    }

    openMedicalCertModal() {
        const studentId = document.getElementById('studentId').value;
        if (!studentId) {
            alert('Сначала выберите ученика');
            return;
        }

        this.currentStudentId = studentId;
        this.currentStudentName = document.getElementById('name').value;

        document.getElementById('medicalCertStudentId').value = studentId;

        // Сбрасываем форму
        document.getElementById('certStartDate').value = '';
        document.getElementById('certEndDate').value = '';
        document.getElementById('medicalCertAlert').classList.add('d-none');
        document.getElementById('certPreview').classList.add('d-none');

        // Скрываем историю, показываем форму
        document.getElementById('medicalCertListSection').style.display = 'none';
        document.getElementById('medicalCertFormSection').style.display = 'block';

        // Загружаем историю справок
        this.loadCertificates();

        // Показываем модальное окно
        const modal = new bootstrap.Modal(document.getElementById('medicalCertificateModal'));
        modal.show();
    }

    async addMedicalCertificate() {
        const startDate = document.getElementById('certStartDate').value;
        const endDate = document.getElementById('certEndDate').value;
        const studentId = this.currentStudentId;

        if (!startDate || !endDate) {
            this.showCertAlert('Заполните обе даты', 'warning');
            return;
        }

        // Проверяем формат даты
        const dateRegex = /^\d{2}\.\d{2}\.\d{4}$/;
        if (!dateRegex.test(startDate) || !dateRegex.test(endDate)) {
            this.showCertAlert('Используйте формат ДД.ММ.ГГГГ', 'warning');
            return;
        }

        const addBtn = document.getElementById('addMedicalCert');
        const originalText = addBtn.innerHTML;
        addBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Обработка...';
        addBtn.disabled = true;

        try {
            const response = await fetch(`/api/student/${studentId}/medical-certificate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    start_date: startDate,
                    end_date: endDate
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка сервера');
            }

            const result = await response.json();

            if (result.success) {
                // Обновляем баланс на странице
                this.updateBalanceAfterCert(result);

                // Обновляем список справок
                await this.loadCertificates();

                // Показываем сообщение об успехе
                this.showCertAlert(result.message, 'success');

                // Очищаем форму
                document.getElementById('certStartDate').value = '';
                document.getElementById('certEndDate').value = '';
                document.getElementById('certPreview').classList.add('d-none');

                // Показываем историю
                this.showCertHistory();

                // Показываем уведомление
                this.showCertSuccessToast(result);
            } else {
                throw new Error(result.error || 'Ошибка при обработке справки');
            }
        } catch (error) {
            this.showCertAlert(error.message, 'danger');
        } finally {
            addBtn.innerHTML = '<i class="fas fa-plus me-1"></i> Добавить справку';
            addBtn.disabled = false;
        }
    }

    async loadCertificates() {
        try {
            const response = await fetch(`/api/student/${this.currentStudentId}/medical-certificates`);

            if (response.ok) {
                const result = await response.json();
                this.certificates = result.certificates || [];
                this.renderCertificates();
            }
        } catch (error) {
            console.error('Error loading certificates:', error);
        }
    }

    renderCertificates() {
        const tableBody = document.getElementById('medicalCertTableBody');
        const noCertsDiv = document.getElementById('noCertificates');

        if (!tableBody) return;

        if (!this.certificates.length) {
            tableBody.innerHTML = '';
            if (noCertsDiv) {
                noCertsDiv.style.display = 'block';
            }
            return;
        }

        if (noCertsDiv) {
            noCertsDiv.style.display = 'none';
        }

        const html = this.certificates.map(cert => `
            <tr id="cert-row-${cert.id}">
                <td>
                    <strong>${cert.start_date}</strong> — <strong>${cert.end_date}</strong>
                </td>
                <td>
                    <span class="badge bg-danger">${cert.missed_classes} занятий</span>
                </td>
                <td>${cert.processed_date}</td>
                <td>
                    <button type="button" class="btn btn-sm btn-outline-danger"
                            onclick="window.medicalCertManager.deleteCertificate(${cert.id})"
                            data-bs-toggle="tooltip" title="Удалить справку">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');

        tableBody.innerHTML = html;
    }

    async deleteCertificate(certificateId) {
        if (!confirm('Удалить эту справку? Занятия будут сняты с баланса ученика.')) {
            return;
        }

        try {
            const response = await fetch(`/api/student/${this.currentStudentId}/medical-certificate/${certificateId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка сервера');
            }

            const result = await response.json();

            if (result.success) {
                // Обновляем баланс
                this.updateBalanceAfterDeletion(result);

                // Удаляем строку из таблицы
                const row = document.getElementById(`cert-row-${certificateId}`);
                if (row) {
                    row.remove();
                }

                // Обновляем список справок
                this.certificates = this.certificates.filter(c => c.id !== certificateId);

                // Показываем сообщение
                this.showCertAlert(result.message, 'success');

                // Показываем уведомление
                this.showDeletionToast(result);
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            this.showCertAlert(error.message, 'danger');
        }
    }

    updateBalanceAfterCert(result) {
        // Обновляем остаток занятий на основной странице
        const balanceInput = document.getElementById('classes_remaining');
        if (balanceInput) {
            balanceInput.value = result.new_balance;

            // Анимация
            balanceInput.classList.add('highlight');
            setTimeout(() => balanceInput.classList.remove('highlight'), 1000);

            // Обновляем статус
            if (window.paymentManager && window.paymentManager.updateBalanceStatus) {
                window.paymentManager.updateBalanceStatus(result.new_balance);
            }
        }
    }

    updateBalanceAfterDeletion(result) {
        // Обновляем остаток после удаления справки
        const balanceInput = document.getElementById('classes_remaining');
        if (balanceInput) {
            const currentBalance = parseInt(balanceInput.value) || 0;
            balanceInput.value = result.new_balance;

            // Анимация
            balanceInput.classList.add('highlight-red');
            setTimeout(() => balanceInput.classList.remove('highlight-red'), 1000);

            // Обновляем статус
            if (window.paymentManager && window.paymentManager.updateBalanceStatus) {
                window.paymentManager.updateBalanceStatus(result.new_balance);
            }
        }
    }

    async updateCertPreview() {
        const startDate = document.getElementById('certStartDate').value;
        const endDate = document.getElementById('certEndDate').value;

        if (!startDate || !endDate) {
            document.getElementById('certPreview').classList.add('d-none');
            return;
        }

        // Простой предпросмотр без расчета занятий
        const start = new Date(startDate.split('.').reverse().join('-'));
        const end = new Date(endDate.split('.').reverse().join('-'));
        const diffTime = Math.abs(end - start);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;

        const previewText = `
            <div class="text-start">
                <div class="row align-items-center mb-2">
                    <div class="col-6">
                        <h6 class="mb-0">Период болезни</h6>
                    </div>
                    <div class="col-6 text-end">
                        <span class="badge bg-info">${diffDays} дней</span>
                    </div>
                </div>
                <hr class="my-2">
                <div class="text-center">
                    <p class="mb-1"><small class="text-muted">Система автоматически рассчитает</small></p>
                    <p class="mb-0"><strong>количество пропущенных занятий</strong></p>
                    <p class="mb-0 small text-muted">на основе расписания ученика</p>
                </div>
            </div>
        `;

        document.getElementById('certPreviewText').innerHTML = previewText;
        document.getElementById('certPreview').classList.remove('d-none');
    }

    toggleCertHistory() {
        const listSection = document.getElementById('medicalCertListSection');
        const formSection = document.getElementById('medicalCertFormSection');
        const historyBtn = document.getElementById('showCertHistory');

        if (listSection.style.display === 'none') {
            listSection.style.display = 'block';
            formSection.style.display = 'none';
            historyBtn.innerHTML = '<i class="fas fa-plus me-1"></i> Добавить справку';
            historyBtn.classList.remove('btn-outline-info');
            historyBtn.classList.add('btn-info');
        } else {
            listSection.style.display = 'none';
            formSection.style.display = 'block';
            historyBtn.innerHTML = '<i class="fas fa-history me-1"></i> История справок';
            historyBtn.classList.remove('btn-info');
            historyBtn.classList.add('btn-outline-info');
        }
    }

    showCertAlert(message, type = 'danger') {
        const alertDiv = document.getElementById('medicalCertAlert');
        alertDiv.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        alertDiv.classList.remove('d-none');
    }

    showCertSuccessToast(result) {
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }

        const toastId = 'cert-toast-' + Date.now();
        const toastHTML = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header bg-info text-white">
                    <strong class="me-auto">
                        <i class="fas fa-file-medical me-2"></i>
                        Справка обработана
                    </strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    <div class="mb-2">
                        <strong>${this.currentStudentName}</strong>
                    </div>
                    <div class="row small">
                        <div class="col-6">Период:</div>
                        <div class="col-6 text-end">${result.start_date} — ${result.end_date}</div>
                    </div>
                    <div class="row small">
                        <div class="col-6">Возвращено:</div>
                        <div class="col-6 text-end"><span class="badge bg-success">+${result.missed_classes} занятий</span></div>
                    </div>
                    <div class="row small">
                        <div class="col-6">Новый баланс:</div>
                        <div class="col-6 text-end"><strong>${result.new_balance} занятий</strong></div>
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

        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    showDeletionToast(result) {
        let toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toastContainer';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }

        const toastId = 'cert-delete-toast-' + Date.now();
        const toastHTML = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header bg-warning text-white">
                    <strong class="me-auto">
                        <i class="fas fa-trash me-2"></i>
                        Справка удалена
                    </strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    <div class="mb-2">
                        <strong>${this.currentStudentName}</strong>
                    </div>
                    <div class="row small">
                        <div class="col-6">Снято занятий:</div>
                        <div class="col-6 text-end"><span class="badge bg-danger">-${result.classes_removed} занятий</span></div>
                    </div>
                    <div class="row small">
                        <div class="col-6">Новый баланс:</div>
                        <div class="col-6 text-end"><strong>${result.new_balance} занятий</strong></div>
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

        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.medicalCertManager = new MedicalCertificateManager();
});