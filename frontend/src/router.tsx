import { Navigate, createBrowserRouter } from 'react-router-dom';
import { AuthGate } from './components/layout/AuthGate';
import { ProtectedLayout } from './components/layout/ProtectedLayout';
import HoldingsPage from './pages/HoldingsPage';
import LoginPage from './pages/LoginPage';
import LossesPage from './pages/LossesPage';
import StocksPage from './pages/StocksPage';
import StrategiesPage from './pages/StrategiesPage';
import TrackerPage from './pages/TrackerPage';

// AuthGate waits for GET /auth/me. /login is public; everything else sits behind ProtectedLayout (login required).
// `handle.title` is what the TopBar shows for each route.
export const router = createBrowserRouter([
  {
    element: <AuthGate />,
    children: [
      { path: '/login', element: <LoginPage /> },
      {
        element: <ProtectedLayout />,
        children: [
          { path: '/', element: <Navigate to="/stocks" replace /> },
          { path: '/stocks', element: <StocksPage />, handle: { title: 'Stocks' } },
          { path: '/tracker', element: <TrackerPage />, handle: { title: 'Tracker' } },
          { path: '/holdings', element: <HoldingsPage />, handle: { title: 'Holdings' } },
          { path: '/losses', element: <LossesPage />, handle: { title: 'Loss Analysis' } },
          { path: '/strategies', element: <StrategiesPage />, handle: { title: 'Strategies' } },
          { path: '/account', element: <Navigate to="/strategies" replace /> },
          { path: '*', element: <Navigate to="/stocks" replace /> },
        ],
      },
    ],
  },
]);
