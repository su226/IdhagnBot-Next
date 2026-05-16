import {
  CircularProgress,
  createTheme,
  CssBaseline,
  ThemeProvider,
  Typography,
} from "@mui/material";
import { lazy, StrictMode, Suspense } from "react"
import { createRoot } from "react-dom/client"
import { createBrowserRouter, isRouteErrorResponse, useRouteError } from "react-router";
import { RouterProvider } from "react-router/dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Login from "./routes/Login";
import PrimaryText from "./components/PrimaryH2";
import EmptyContainer from "./components/EmptyContainer";

function ErrorBoundary() {
  const error = useRouteError();
  if (isRouteErrorResponse(error)) {
    return (
      <EmptyContainer>
        <Typography variant="h2" component="h1">
          <PrimaryText>{error.status}</PrimaryText> 
          {" "}
          {error.statusText}
        </Typography>
        <Typography>{error.data}</Typography>
      </EmptyContainer>
    );
  } else if (error instanceof Error) {
    return (
      <EmptyContainer>
        <Typography variant="h2" component="h1">
          <PrimaryText>错误</PrimaryText>
        </Typography>
        <Typography>{error.message || "未知错误"}</Typography>
        <pre style={{ textAlign: "start", overflowX: "auto" }}>{error.stack}</pre>
      </EmptyContainer>
    );
  } else {
    return (
      <EmptyContainer>
        <Typography variant="h2" component="h1">
          未知
          <PrimaryText>错误</PrimaryText>
        </Typography>
        <Typography>{String(error)}</Typography>
      </EmptyContainer>
    );
  }
}

const Dashboard = lazy(() => import("./routes/Dashboard"));
const Config = lazy(() => import("./routes/Config"));

const router = createBrowserRouter([
  {
    path: "/",
    ErrorBoundary,
    children: [
      { index: true, element: <Login /> },
      { path: "/dashboard", element: <Dashboard /> },
      { path: "/config", element: <Config /> },
    ],
  },
], {
  basename: "/idhagnbot-webui",
});

const theme = createTheme({
  colorSchemes: {
    dark: true,
  },
});

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Suspense fallback={<EmptyContainer><CircularProgress /></EmptyContainer>}>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </Suspense>
    </ThemeProvider>
  </StrictMode>,
);
