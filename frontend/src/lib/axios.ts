import axios from 'axios';


console.log(123123, import.meta.env.VITE_API_URL)
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:58000/api',
});

export default api;