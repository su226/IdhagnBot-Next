import { Button, Checkbox, FormControlLabel, Snackbar, TextField, Typography } from "@mui/material";
import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import PrimaryText from "../components/PrimaryH2";
import EmptyContainer from "../components/EmptyContainer";
import { Result } from "../utils/response";
import z from "zod";

const LoginData = z.object({
  plugins: z.array(z.string()),
});

type LoginData = z.infer<typeof LoginData>;

export default function Login() {
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState(localStorage.token);
  const [remember, setRemember] = useState(Boolean(localStorage.token));
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const navigate = useNavigate();
  const location = useLocation();

  const login = async (token: string) => {
    setLoading(true);
    try {
      const response = await fetch("/idhagnbot-api/authenticate", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
      });
      const result = Result.parse(await response.json());
      if (!result.success) {
        setLoading(false);
        setSnackbarOpen(true);
        setSnackbarMessage(result.message);
        return;
      }
      const data = LoginData.parse(result.data);
      sessionStorage.token = token;
      sessionStorage.plugins = JSON.stringify(data.plugins);
      if (remember) {
        localStorage.token = token;
      }
      navigate(location.state?.back ?? "/dashboard");
    } catch (e) {
      setLoading(false);
      setSnackbarOpen(true);
      setSnackbarMessage(String(e));
    }
  };

  useEffect(() => {
    if (localStorage.token) {
      login(localStorage.token);
    }
  }, []);

  const onKeyUp = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter") {
      login(token);
    }
  };

  return (
    <EmptyContainer>
      <Typography variant="h2" component="h1">
        <PrimaryText>IdhagnBot</PrimaryText>
        {" WebUI"}
      </Typography>
      <TextField
        label="Token"
        disabled={loading}
        type="password"
        value={token}
        onChange={event => setToken(event.target.value)}
        onKeyUp={onKeyUp}
      />
      <FormControlLabel
        control={
          <Checkbox
            checked={remember}
            onChange={event => setRemember(event.target.checked)}
          />
        }
        disabled={loading}
        label="记住 Token"
      />
      <Button variant="contained" disabled={loading} onClick={() => login(token)}>登录</Button>
      <Snackbar
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={() => setSnackbarOpen(false)}
        message={snackbarMessage}
      />
    </EmptyContainer>
  );
};
