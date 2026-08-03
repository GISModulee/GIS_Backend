import axiosInstance from "@/api/axiosInstance.js";

export const authService = {
    login: async (email, password) => {
        // Modify the endpoint as needed depending on your backend
        const response = await axiosInstance.post("/login", { email, password });
        return response.data;
    }
};

