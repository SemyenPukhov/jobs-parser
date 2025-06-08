import axios from 'axios';

// Отладочная информация
console.log('Environment variables:', import.meta.env);
console.log('VITE_API_URL:', import.meta.env.VITE_API_URL);

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:58000/api',
});

// Добавляем перехватчик для отладки запросов
api.interceptors.request.use(request => {
  console.log('Starting Request:', request);
  return request;
});

api.interceptors.response.use(
  response => {
    console.log('Response:', response);
    return response;
  },
  error => {
    console.error('Response Error:', error);
    return Promise.reject(error);
  }
);

export default api;