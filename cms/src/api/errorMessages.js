/**
 * Maps HTTP status codes to plain-language error messages.
 */
const statusMessages = {
  400: 'The request was invalid. Please check your input.',
  401: 'Session expired. Please refresh and log in again.',
  403: 'You do not have permission to perform this action.',
  404: 'The requested item was not found.',
  409: 'A conflict occurred. The item may have been modified by someone else.',
  413: 'The file is too large to upload.',
  422: 'Some fields are invalid. Please check your input.',
  429: 'Too many requests. Please wait a moment and try again.',
  500: 'Something went wrong on the server. The error has been logged.',
  502: 'The server is temporarily unavailable. Please try again shortly.',
  503: 'The server is temporarily unavailable. Please try again shortly.',
}

export function getErrorMessage(status, serverDetail) {
  // Use server-provided user_message if available
  if (serverDetail?.user_message) {
    return serverDetail.user_message
  }
  return statusMessages[status] || `Unexpected error (${status}). Please try again.`
}

export function getErrorSeverity(status) {
  if (status === 401) return 'warn'
  if (status >= 500) return 'error'
  return 'warn'
}
