import axios, { AxiosError, AxiosInstance, AxiosResponse } from 'axios';
import type { User, OktaUser, AuthResponse, RegisterRequest } from '@/types/auth';
import type { Folder, CreateFolderRequest, UpdateFolderRequest } from '@/types/folder';
import type { Document } from '@/types/document';
import type { RAGQuery, RAGResponse } from '@/types/rag';
import type { ChatSessionResponse, ChatSessionWithMessages, ChatMessageResponse, ChatMessageCreate } from '@/types/chat';
import { validate as isUUID } from 'uuid';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

class APIClient {
	private http: AxiosInstance;
	private token: string | null = null;
	private abortController: AbortController | null = null;

	constructor() {
		this.http = axios.create({
			baseURL: `${API_BASE_URL}${API_PREFIX}`,
		});

		this.abortController = typeof window !== 'undefined' ? new AbortController() : null;

		// Attach Authorization header when token set
		this.http.interceptors.request.use((config) => {
			if (this.token) {
				config.headers = config.headers || {};
				config.headers.Authorization = `Bearer ${this.token}`;
			}
			
			// Attach login type from localStorage
			if (typeof window !== 'undefined') {
				const loginType = localStorage.getItem('loginType') || 'radex';
				config.headers['X-Login-Type'] = loginType;
			}
			
			if (this.abortController) {
				config.signal = this.abortController.signal;
			}
			return config;
		});

		// Initialize from localStorage if available in browser
		if (typeof window !== 'undefined') {
			const saved = localStorage.getItem('auth_token');
			if (saved) {
				this.setToken(saved);
			}
		}
	}

	setToken(token: string | null) {
		this.token = token;
		if (typeof window !== 'undefined') {
			if (token) localStorage.setItem('auth_token', token);
			else localStorage.removeItem('auth_token');
			console.log("Token set in LocalStorage");
			// console.log('Token set in LocalStorage:', token);
		}
		// When logging out, cancel any in-flight requests
		if (!token && this.abortController) {
			this.abortController.abort();
			this.abortController = new AbortController();
		}
	}

	// Auth
	async login(username: string, password: string): Promise<AuthResponse> {
		const form = new URLSearchParams();
		form.append('username', username);
		form.append('password', password);

		const tokenResp = await this.http.post('/auth/login', form, {
			headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		});
		const access_token: string = tokenResp.data.access_token;
		this.setToken(access_token);
		const user = await this.getCurrentUser({ headers: { "X-Login-Type": "radex" } });
		return {
			access_token,
			token_type: tokenResp.data.token_type ?? 'bearer',
			expires_in: 0,
			user,
		};
	}

	// okta-login
	async syncFirebaseUser(firebaseResult: any) {
		const tokenResp = await this.http.post('/auth/okta_login', firebaseResult);
		const access_token: string = tokenResp.data.access_token; // ✅ extract string
		this.setToken(access_token); // sets Authorization: Bearer <token>
		
		return tokenResp.data; // { access_token, token_type }
	}
	async register(payload: RegisterRequest): Promise<AuthResponse> {
		await this.http.post('/auth/register', payload);
		return this.login(payload.username, payload.password);
	}

	async getCurrentUser(): Promise<User> {
		const resp = await this.http.get('/auth/me');
		return resp.data as User;
	}

	// Folders
	async getFolders(): Promise<Folder[]> {
		const resp = await this.http.get('/folders/');
		return resp.data as Folder[];
	}

	async createFolder(payload: CreateFolderRequest): Promise<Folder> {
		const resp = await this.http.post('/folders/', payload);
		return resp.data as Folder;
	}

	async getFolder(folderId: string): Promise<Folder> {
		const resp = await this.http.get(`/folders/${folderId}`);
		return resp.data as Folder;
	}

	async updateFolder(folderId: string, payload: UpdateFolderRequest): Promise<Folder> {
		const resp = await this.http.put(`/folders/${folderId}`, payload);
		return resp.data as Folder;
	}

	// Documents
	async getFolderDocuments(folderId: string): Promise<Document[]> {
		const resp = await this.http.get(`/folders/${folderId}/documents`);
		return resp.data as Document[];
	}

	async uploadDocument(folderId: string, file: File): Promise<unknown> {
		const formData = new FormData();
		formData.append('file', file);
		const resp = await this.http.post(`/folders/${folderId}/documents`, formData, {
			headers: { 'Content-Type': 'multipart/form-data' },
		});
		return resp.data;
	}

	async deleteDocument(documentId: string): Promise<void> {
		await this.http.delete(`/documents/${documentId}`);
	}

	async downloadDocument(documentId: string): Promise<AxiosResponse<Blob>> {
		return await this.http.get(`/documents/${documentId}/download`, { responseType: 'blob' });
	}

	// Users (admin)
	async list_users(params?: Record<string, unknown>): Promise<User[]> {
		const resp = await this.http.get('/users/', { params });
		return resp.data as User[];
	}

	async createUser(payload: { email: string; username: string; password: string; is_active: boolean; is_superuser: boolean; }): Promise<User> {
		const resp = await this.http.post('/users/', payload);
		return resp.data as User;
	}

	async updateUser(userId: string, payload: Record<string, unknown>): Promise<User> {
		const resp = await this.http.put(`/users/${userId}`, payload);
		return resp.data as User;
	}

	async deleteUser(userId: string): Promise<void> {
		await this.http.delete(`/users/${userId}`);
	}

	async find_user(params: { email?: string; username?: string }): Promise<User> {
		const resp = await this.http.get('/users/find', { params });
		return resp.data as User;
	}

	// Folder permissions
	async getFolderPermissions(folderId: string): Promise<any[]> {
		const resp = await this.http.get(`/folders/${folderId}/permissions`);
		return resp.data as any[];
	}

	async grantFolderPermission(folderId: string, payload: Record<string, unknown>): Promise<any> {
		const resp = await this.http.post(`/folders/${folderId}/permissions`, payload);
		return resp.data;
	}

	async revokeFolderPermission(folderId: string, userId: string): Promise<void> {
		await this.http.delete(`/folders/${folderId}/permissions/${userId}`);
	}

	// RAG
	async getRAGFolders(): Promise<Folder[]> {
		const resp = await this.http.get('/rag/folders');
		return resp.data as Folder[];
	}

	// async queryRAG(payload: RAGQuery): Promise<RAGResponse> {
	// 	const resp = await this.http.post('/rag/query', payload);
	// 	return resp.data as RAGResponse;
	// }

	async queryRAG(payload: RAGQuery): Promise<RAGResponse> {
	if (!isUUID(payload.session_id)) {
		throw new Error('Invalid sessionId');
	}
	
	// Send payload directly
	const resp = await this.http.post(`/rag/query`, payload);
	return resp.data as RAGResponse;
	}

	// Get all chat sessions for the current user
	async getChatSessions(): Promise<ChatSessionResponse[]> {
		const resp = await this.http.get('/chat/sessions');
		return resp.data as ChatSessionResponse[];
	}

	// Create a new chat session (optional title)
	async createChatSession(title?: string): Promise<ChatSessionResponse> {
		const payload = title ? { title } : {};
		const resp = await this.http.post('/chat/sessions', payload);
		return resp.data as ChatSessionResponse;
	}

	// Get all messages for a specific chat session
	async getChatMessages(sessionId: string): Promise<ChatSessionWithMessages> {
	const resp = await this.http.get(`/chat/${sessionId}/messages`);
	return resp.data as ChatSessionWithMessages;
	}

	// Send a new message in a chat session
	async sendChatMessage(
	sessionId: string,
	payload: ChatMessageCreate
	): Promise<ChatMessageResponse> {
	const resp = await this.http.post(`/chat/${sessionId}/messages`, payload);
	return resp.data as ChatMessageResponse;
	}

	// // Delete a chat session and its messages
	// async deleteChatSession(sessionId: string) {
	// 	return await this.http.delete(`/chat/sessions/${sessionId}`);
	// }

	async deleteChatSession(sessionId: string) {
    return await this.http.delete(`/chat/sessions/${sessionId}`, { 
        validateStatus: (status) => status === 204 
    });
	}

	async updateChatSession(sessionId: string, title: string): Promise<ChatSessionResponse> {
	const resp = await this.http.patch(`/chat/sessions/${sessionId}`, { title });
	return resp.data as ChatSessionResponse;
	}
	
}

const apiClient = new APIClient();
export default apiClient; 