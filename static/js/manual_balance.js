// static/js/manual_balance.js - исправленный метод saveManualBalance
async function saveManualBalance() {
    const newBalance = document.getElementById('newBalance').value;
    const studentId = this.currentStudentId;
    const reason = document.getElementById('balanceReason').value || 'Ручная корректировка';

    if (!newBalance || newBalance < 0) {
        this.showBalanceAlert('Введите корректное значение баланса', 'warning');
        return;
    }

    const saveBtn = document.getElementById('saveManualBalance');
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
                // Также обновляем в PaymentManager
            if (window.paymentManager) {
                window.paymentManager.currentBalance = result.new_balance;
                window.paymentManager.updateBalanceStatus(result.new_balance);
            }
            // Обновляем дату оплаты если изменилась
            if (result.payment_date_info) {
                // Можно обновить поле expected_payment_date
            }

            // Показываем сообщение об успехе
            this.showBalanceAlert(result.message, 'success');

            // Закрываем модальное окно через 2 секунды
            setTimeout(() => {
                const modal = bootstrap.Modal.getInstance(document.getElementById('manualBalanceModal'));
                if (modal) {
                    modal.hide();
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
    updateMainBalanceField(result) {
    // Обновляем поле на основной странице
    const balanceInput = document.getElementById('classes_remaining');
    if (balanceInput) {
        balanceInput.value = result.new_balance;

        // Анимация
        const changeType = result.new_balance > result.old_balance ? 'highlight' : 'highlight-red';
        balanceInput.classList.add(changeType);
        setTimeout(() => balanceInput.classList.remove(changeType), 1000);
    }
}
}