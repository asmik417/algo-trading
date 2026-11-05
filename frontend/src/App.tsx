import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { isApiError } from './api/client';
import { ToastProvider } from './components/ui/Toast';
import { router } from './router';
import { AuthProvider } from './store/auth';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // One retry for hiccups, but never for 401: that means "signed out", and retrying cannot fix it.
      retry: (failureCount, error) =>
        !(isApiError(error) && error.status === 401) && failureCount < 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
