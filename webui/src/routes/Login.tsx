import {
  Button,
  Checkbox,
  FormControlLabel,
  Snackbar,
  TextField,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useLocation, useNavigate } from "react-router";
import PrimaryText from "../components/PrimaryH2";
import EmptyContainer from "../components/EmptyContainer";
import { Result } from "../utils/response";
import z from "zod";

const LoginData = z.object({
  plugins: z.array(z.string()),
});

type LoginData = z.infer<typeof LoginData>;

type LoginResult = { success: boolean; message: string };

async function login(token: string): Promise<LoginResult> {
  try { 
    const response = await fetch("/idhagnbot-api/authenticate", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`
      },
    });
    const result = Result.parse(await response.json());
    if (!result.success) {
      return { success: false, message: result.message };
    }
    const data = LoginData.parse(result.data);
    sessionStorage.token = token;
    sessionStorage.plugins = JSON.stringify(data.plugins);
    return { success: true, message: "" };
  } catch (e) {
    return { success: false, message: String(e) };
  }
};

export default function Login() {
  const rememberedToken = localStorage.token ?? "";
  const hasRememberedToken = Boolean(rememberedToken);
  const [token, setToken] = useState(rememberedToken);
  const [remember, setRemember] = useState(hasRememberedToken);
  const [loading, setLoading] = useState(hasRememberedToken);
  const triedAutoLogin = useRef(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const navigate = useNavigate();
  const location = useLocation();

  const afterLogin = useCallback((result: LoginResult) => {
    if (result.success) {
      navigate(location.state?.back ?? "/dashboard");
    } else {
      setSnackbarOpen(true);
      setSnackbarMessage(result.message);
      setLoading(false);
    }
  }, [navigate, location]);

  useEffect(() => {
    if (triedAutoLogin.current) {
      return;
    }
    triedAutoLogin.current = true;
    const rememberedToken = localStorage.token;
    if (rememberedToken) {
      login(rememberedToken).then(result => {
        // 不在自动登录开始时清除记住的 Token，等到自动登录失败时才清除，防止自动登录过程中关闭页面
        // 意外丢失登录状态。
        if (!result.success) {
          delete localStorage.token;
        }
        afterLogin(result);
      });
    }
  }, [afterLogin]);

  const manualLogin = () => {
    setLoading(true);
    // 手动登录时，先清除保存的 Token，否则本次未记住 Token 而之前记住了 Token 时之前记住的 Token
    // 不会被清除。
    delete localStorage.token;
    login(rememberedToken).then(result => {
      // 登录成功后再记住 Token。
      if (result.success && remember) {
        localStorage.token = token;
      }
      afterLogin(result);
    });
  };

  const onKeyUp = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter") {
      manualLogin();
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
        helperText="若忘记 Token，可查看配置文件 config/idhagnbot/webui.yaml"
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
      <Button variant="contained" disabled={loading} onClick={manualLogin}>登录</Button>
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
