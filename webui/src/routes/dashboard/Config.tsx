import {
  Fab,
  Menu,
  MenuItem,
  Snackbar,
  useTheme,
} from "@mui/material";
import { Menu as MenuIcon } from "@mui/icons-material";
import z from "zod";
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { CODE_SUCCESS, Result } from "../../utils/response";
import CodeMirror, { type Extension } from "@uiw/react-codemirror";
import { yamlSchema } from "codemirror-json-schema/yaml";
import classes from "./Config.module.css";

const ConfigGetData = z.object({
  config: z.string(),
  schema: z.any(),
});

type ConfigGetData = z.infer<typeof ConfigGetData>;

export default function Config() {
  const theme = useTheme();
  const dark = theme.palette.mode === "dark";
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [editorValue, setEditorValue] = useState("");
  const [editorExtensions, setEditorExtensions] = useState<Extension[]>([]);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const menuOpen = Boolean(menuAnchor);
  const fetchedRef = useRef(false);

  const doRefreshConfig = async () => {
    try {
      const url = new URL("/idhagnbot-api/config", location.href);
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${sessionStorage.token}`,
        },
      });
      const result = Result.parse(await response.json());
      if (result.code !== CODE_SUCCESS) {
        setSnackbarOpen(true);
        setSnackbarMessage(result.message);
        return;
      }
      const data = ConfigGetData.parse(result.data);
      setEditorValue(data.config);
      setEditorExtensions([yamlSchema(data.schema)]);
      return true;
    } catch (e) {
      setSnackbarOpen(true);
      setSnackbarMessage(String(e));
      return false;
    }
  };

  useEffect(() => {
    if (fetchedRef.current) {
      return;
    }
    fetchedRef.current = true;
    doRefreshConfig();
  }, []);

  const refreshConfig = async () => {
    closeMenu();
    if (await doRefreshConfig()) {
      setSnackbarOpen(true);
      setSnackbarMessage("已刷新");
    }
  };

  const reloadConfig = async () => {
    closeMenu();
    try {
      const url = new URL("/idhagnbot-api/config/reload", location.href);
      const response = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${sessionStorage.token}`,
        },
      });
      const result = Result.parse(await response.json());
      if (result.code !== CODE_SUCCESS) {
        setSnackbarOpen(true);
        setSnackbarMessage(result.message);
        return;
      }
      const data = ConfigGetData.parse(result.data);
      setEditorValue(data.config);
      setEditorExtensions([yamlSchema(data.schema)]);
      setSnackbarOpen(true);
      setSnackbarMessage("已重载并刷新");
    } catch (e) {
      setSnackbarOpen(true);
      setSnackbarMessage(String(e));
    }
  };

  const saveConfig = async () => {
    closeMenu();
    try {
      const url = new URL("/idhagnbot-api/config", location.href);
      const response = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${sessionStorage.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          config: editorValue,
        }),
      });
      const result = Result.parse(await response.json());
      if (result.code !== CODE_SUCCESS) {
        setSnackbarOpen(true);
        setSnackbarMessage(result.message);
        return;
      }
      setSnackbarOpen(true);
      setSnackbarMessage("已保存并重载");
    } catch (e) {
      setSnackbarOpen(true);
      setSnackbarMessage(String(e));
    }
  };

  const openMenu = (event: MouseEvent<HTMLButtonElement>) => {
    setMenuAnchor(event.currentTarget);
  };
  const closeMenu = () => setMenuAnchor(null);

  return (
    <>
      <CodeMirror
        theme={dark ? "dark" : "light"}
        value={editorValue}
        onChange={value => setEditorValue(value)}
        extensions={editorExtensions}
        className={classes.editor}
      />
      <Snackbar
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={() => setSnackbarOpen(false)}
        message={snackbarMessage}
      />
      <Fab
        sx={{ position: "fixed", bottom: 16, right: 16 }}
        color="primary"
        onClick={openMenu}
      >
        <MenuIcon />
      </Fab>
      <Menu
        anchorEl={menuAnchor}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        open={menuOpen}
        onClose={closeMenu}
      >
        <MenuItem onClick={refreshConfig}>刷新</MenuItem>
        <MenuItem onClick={reloadConfig}>重载并刷新</MenuItem>
        <MenuItem onClick={saveConfig}>保存并重载</MenuItem>
      </Menu>
    </>
  );
}
