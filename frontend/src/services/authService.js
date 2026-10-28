import { API_BASE_URL } from "./config";


const TOKEN_KEY = "trustlens_access_token";
const USER_KEY = "trustlens_user";


async function parseResponse(response, fallbackMessage) {
    if (!response.ok) {
        let message = fallbackMessage;

        try {
            const error = await response.json();
            if (Array.isArray(error.detail)) {
                message = error.detail[0]?.msg || message;
            } else {
                message = error.detail || message;
            }
        } catch {
            // Keep the fallback message.
        }

        throw new Error(message);
    }

    return await response.json();
}


function storeAuthentication(authentication) {
    localStorage.setItem(TOKEN_KEY, authentication.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(authentication.user));
    return authentication.user;
}


export function getAccessToken() {
    return localStorage.getItem(TOKEN_KEY);
}


export function getStoredUser() {
    const storedUser = localStorage.getItem(USER_KEY);

    if (!storedUser || !getAccessToken()) {
        return null;
    }

    try {
        return JSON.parse(storedUser);
    } catch {
        clearAuthentication();
        return null;
    }
}


export function clearAuthentication() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem("trustlens_last_claim_id");
}


export async function registerAccount(details) {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(details),
    });
    const authentication = await parseResponse(
        response,
        "Could not create your account."
    );
    return storeAuthentication(authentication);
}


export async function loginAccount(email, password) {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({email, password}),
    });
    const authentication = await parseResponse(
        response,
        "Could not sign in."
    );
    return storeAuthentication(authentication);
}


export async function getCurrentUser() {
    const response = await authenticatedFetch("/auth/me");
    const user = await response.json();
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
}


export async function updateProfile(fullName) {
    const response = await authenticatedFetch("/auth/profile", {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({full_name: fullName}),
    });
    const user = await response.json();
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
}


export async function changePassword(currentPassword, newPassword) {
    const response = await authenticatedFetch("/auth/change-password", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
        }),
    });
    return await response.json();
}


export async function authenticatedFetch(path, options = {}) {
    const token = getAccessToken();
    const headers = new Headers(options.headers || {});

    if (token) {
        headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers,
    });

    if (response.status === 401) {
        clearAuthentication();
        window.dispatchEvent(new Event("trustlens:auth-expired"));
    }

    if (!response.ok) {
        let message = "The request could not be completed.";

        try {
            const error = await response.json();
            if (Array.isArray(error.detail)) {
                message = error.detail[0]?.msg || message;
            } else {
                message = error.detail || message;
            }
        } catch {
            // Keep the fallback message.
        }

        throw new Error(message);
    }

    return response;
}
