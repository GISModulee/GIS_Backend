import { createSlice } from "@reduxjs/toolkit";

const initialState = {
    token: localStorage.getItem("token") || null,
    user: JSON.parse(localStorage.getItem("user")) || null,
    isAuthenticated: !!localStorage.getItem("token"),
    activeCaseId: localStorage.getItem("active_case_id") || null,
    cases: (() => {
        try {
            return JSON.parse(localStorage.getItem("cases_cache")) || [];
        } catch (_) {
            return [];
        }
    })(),
};

const authSlice = createSlice({
    name: "auth",
    initialState,
    reducers: {
        setCredentials(state, action) {
            const { token, user } = action.payload;
            state.token = token;
            if (user) state.user = user;
            state.isAuthenticated = true;
            localStorage.setItem("token", token);
            if (user) localStorage.setItem("user", JSON.stringify(user));
        },
        setActiveCase(state, action) {
            state.activeCaseId = action.payload;
            if (action.payload) {
                localStorage.setItem("active_case_id", action.payload);
            } else {
                localStorage.removeItem("active_case_id");
            }
        },
        setCases(state, action) {
            state.cases = action.payload;
            localStorage.setItem("cases_cache", JSON.stringify(action.payload));
        },
        logout(state) {
            state.token = null;
            state.user = null;
            state.isAuthenticated = false;
            state.activeCaseId = null;
            state.cases = [];
            const theme = localStorage.getItem("theme");
            localStorage.clear();
            if (theme) localStorage.setItem("theme", theme);
        },
    },
});

export const { setCredentials, setActiveCase, setCases, logout } = authSlice.actions;
export default authSlice.reducer;