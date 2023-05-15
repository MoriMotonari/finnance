import { createBrowserRouter } from "react-router-dom";
import { LoginForm } from "../components/auth/LoginForm";
import { SignUpForm } from "../components/auth/SignUpForm";
import CategoriesPage from "../components/category/CategoriesPage";
import NivoPage from "../nivo/NivoPage";
import NotFound from "../pages/404";
import AccountPage from "../pages/Account";
import AccountsPage from "../pages/Accounts";
import DashboardPage from "../pages/Dashboard";
import { AuthLayout, PublicLayout } from "../pages/Layout";
import LogoutPage from "../pages/Logout";
import { RemotesPage } from "../pages/Remotes";
import { TemplatesPage } from "../pages/Templates";
import { TransactionsPage } from "../pages/Transactions";
import { AuthRoute } from "./Route";

export const FinnanceRouter = createBrowserRouter([
    {
        element: <AuthRoute>
            <AuthLayout />
        </AuthRoute>,
        children: [{
            index: true,
            element: <DashboardPage />,
        }, {
            path: "logout",
            element: <LogoutPage />
        }, {
            path: "accounts/:id",
            element: <AccountPage />,
        }, {
            path: "accounts",
            element: <AccountsPage />
        }, {
            path: "categories",
            element: <CategoriesPage />
        }, {
            path: "analytics",
            element: <NivoPage />
        }, {
            path: "remotes",
            element: <RemotesPage />
        }, {
            path: "transactions",
            element: <TransactionsPage />
        }, {
            path: "templates",
            element: <TemplatesPage />
        }, {
            path: "*",
            element: <NotFound />
        }]
    }, {
        element: <PublicLayout />,
        children: [{
            path: "login",
            element: <LoginForm />
        }, {
            path: "register",
            element: <SignUpForm />
        }]
    }
]);