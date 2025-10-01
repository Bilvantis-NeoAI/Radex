import { twMerge } from 'tailwind-merge';
import clsx from 'clsx';

export function cn(...inputs: any[]): string {
	return twMerge(clsx(inputs));
}

export function getErrorMessage(error: unknown, fallback: string = 'An error occurred'): string {
	// Axios-style error handling
	const maybeAxios = error as any;
	const detail = maybeAxios?.response?.data?.detail || maybeAxios?.response?.data?.message;
	if (detail && typeof detail === 'string') return detail;

	if (maybeAxios?.message && typeof maybeAxios.message === 'string') return maybeAxios.message;

	if (error instanceof Error) return error.message || fallback;
	return fallback;
} 