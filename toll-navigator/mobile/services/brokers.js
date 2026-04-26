import api from './api';

// Get brokers list with pagination and filters
// params: { page, limit, search, state, min_rating }
export const getBrokers = async (params = {}) => {
  const { data } = await api.get('/api/brokers', { params });
  return data;
};

// Get broker details with reviews (reviews_page for pagination)
export const getBrokerDetail = async (brokerId, reviewsPage = 1) => {
  const { data } = await api.get(`/api/brokers/${brokerId}`, {
    params: reviewsPage > 1 ? { reviews_page: reviewsPage } : undefined,
  });
  return data;
};

// Create new broker
export const createBroker = async (brokerData) => {
  const { data } = await api.post('/api/brokers', brokerData);
  return data;
};

// Add review to existing broker
export const addBrokerReview = async (brokerId, reviewData) => {
  const { data } = await api.post(`/api/brokers/${brokerId}/reviews`, reviewData);
  return data;
};

// Create broker and add first review
export const createBrokerWithReview = async (brokerData, reviewData) => {
  const broker = await createBroker(brokerData);
  const review = await addBrokerReview(broker.id, reviewData);
  return { broker, review };
};

// Update review
export const updateBrokerReview = async (brokerId, reviewId, reviewData) => {
  const { data } = await api.put(`/api/brokers/${brokerId}/reviews/${reviewId}`, reviewData);
  return data;
};

// Delete review
export const deleteBrokerReview = async (brokerId, reviewId) => {
  const { data } = await api.delete(`/api/brokers/${brokerId}/reviews/${reviewId}`);
  return data;
};
