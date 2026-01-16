// visits_today_api.js - API функции для работы с посещениями
const visitsTodayApi = {
    // Загрузка мест тренировок
    async loadPlaces() {
        try {
            const response = await fetch('/visits-today/get-places');
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка загрузки мест:', error);
            throw error;
        }
    },

    // Загрузка тренировок для места
    async loadTrainings(placeId) {
        try {
            const response = await fetch(`/visits-today/get-trainings/${placeId}`);
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка загрузки тренировок:', error);
            throw error;
        }
    },

    // Загрузка студентов для тренировки
    async loadStudents(scheduleId) {
        try {
            const response = await fetch(`/visits-today/get-students/${scheduleId}`);
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка загрузки студентов:', error);
            throw error;
        }
    },

    // Поиск дополнительного студента
    async searchStudent(query) {
        try {
            const response = await fetch(`/visits-today/search-extra-student?query=${encodeURIComponent(query)}`);
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка поиска:', error);
            throw error;
        }
    },

    // Сохранение посещений
    async saveAttendance(data) {
        try {
            const response = await fetch('/visits-today/save-attendance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка сохранения:', error);
            throw error;
        }
    },

    // Получение статуса посещений
    async getAttendanceStatus(scheduleId) {
        try {
            const response = await fetch(`/visits-today/get-attendance-status/${scheduleId}`);
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка получения статуса:', error);
            throw error;
        }
    }
};