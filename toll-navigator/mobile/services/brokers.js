import api from './api';

// Получить список брокеров с пагинацией и фильтрами
// params: { page, limit, search, state, min_rating }
export const getBrokers = async (params = {}) => {
  const { data } = await api.get('/api/brokers', { params });
  return data;
};

// Получить детали брокера с отзывами (reviews_page — пагинация отзывов)
export const getBrokerDetail = async (brokerId, reviewsPage = 1) => {
  const { data } = await api.get(`/api/brokers/${brokerId}`, {
    params: reviewsPage > 1 ? { reviews_page: reviewsPage } : undefined,
  });
  return data;
};

// Создать нового брокера
export const createBroker = async (brokerData) => {
  const { data } = await api.post('/api/brokers', brokerData);
  return data;
};

// Добавить отзыв к существующему брокеру
export const addBrokerReview = async (brokerId, reviewData) => {
  const { data } = await api.post(`/api/brokers/${brokerId}/reviews`, reviewData);
  return data;
};

// Создать брокера и сразу добавить первый отзыв
export const createBrokerWithReview = async (brokerData, reviewData) => {
  const broker = await createBroker(brokerData);
  const review = await addBrokerReview(broker.id, reviewData);
  return { broker, review };
};

// Обновить отзыв
export const updateBrokerReview = async (brokerId, reviewId, reviewData) => {
  const { data } = await api.put(`/api/brokers/${brokerId}/reviews/${reviewId}`, reviewData);
  return data;
};

// Удалить отзыв
export const deleteBrokerReview = async (brokerId, reviewId) => {
  const { data } = await api.delete(`/api/brokers/${brokerId}/reviews/${reviewId}`);
  return data;
};
