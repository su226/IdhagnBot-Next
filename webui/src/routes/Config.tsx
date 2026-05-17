import DashboardContainer from "../components/DashboardContainer";
import {
  AppBar,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Slide,
  Snackbar,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import { Close, Delete, Folder, Save } from "@mui/icons-material";
import z from "zod";
import React, { forwardRef, useState } from "react";
import { Result } from "../utils/response";
import type { TransitionProps } from "@mui/material/transitions";
import CodeMirror, { type Extension } from "@uiw/react-codemirror";
import { shell } from "@codemirror/legacy-modes/mode/shell";
import { StreamLanguage } from "@codemirror/language";
import { yamlSchema } from "codemirror-json-schema/yaml";
import { jsonSchema } from "codemirror-json-schema";
import classes from "./Config.module.css";

const ConfigFile = z.object({
  path: z.string(),
  type: z.literal(["shared", "session", "dotenv", "other"]),
  description: z.string(),
  exist: z.boolean(),
});

type ConfigFile = z.infer<typeof ConfigFile>;

const ConfigsData = z.object({
  configs: z.array(ConfigFile),
});

type ConfigsData = z.infer<typeof ConfigsData>;

const ConfigGetData = z.object({
  config: z.string(),
  schema: z.any(),
});

type ConfigGetData = z.infer<typeof ConfigGetData>;

const ConfigSetDeleteData = z.object({
  reloaded: z.boolean(),
});

type ConfigSetDeleteData = z.infer<typeof ConfigSetDeleteData>;

const SlideUp = forwardRef(function Transition(
  props: TransitionProps & { children: React.ReactElement<unknown> },
  ref: React.Ref<unknown>,
) {
  return <Slide direction="up" ref={ref} {...props} />;
});

function ConfigSelectDialog(props: {
  open?: boolean,
  onSelect?: (file: string) => void,
  onDelete?: (file: string) => void,
  onCancel?: () => void,
  configs?: ConfigFile[],
}) {
  const open = props.open ?? false;
  const onSelect = props.onSelect ?? (() => {});
  const onDelete = props.onDelete ?? (() => {});
  const onCancel = props.onCancel ?? (() => {});
  const configs = props.configs ?? [];
  const [customFileDialogOpen, setCustomFileDialogOpen] = useState(false);
  const [customFileName, setCustomFileName] = useState("");
  const [confirmDeleteDialogOpen, setConfirmDeleteDialogOpen] = useState(false);
  const [deleteFileName, setDeleteFileName] = useState("");

  const selectCustomFile = () => {
    setCustomFileDialogOpen(false);
    onSelect(customFileName);
  };

  const askDeleteFile = (fileName: string) => {
    setDeleteFileName(fileName);
    setConfirmDeleteDialogOpen(true);
  };

  const confirmDeleteFile = () => {
    setConfirmDeleteDialogOpen(false);
    onDelete(deleteFileName);
  };

  return (
    <Dialog
      fullScreen
      open={open}
      onClose={onCancel}
      slots={{ transition: SlideUp }}
    >
      <AppBar sx={{ position: 'relative' }}>
        <Toolbar>
          <IconButton
            edge="start"
            color="inherit"
            onClick={onCancel}
            aria-label="close"
          >
            <Close />
          </IconButton>
          <Typography sx={{ ml: 2 }} variant="h6" component="div">
            选择配置文件
          </Typography>
        </Toolbar>
      </AppBar>
      <List>
        {configs.map(file =>
          <ListItem
            key={file.path} 
            secondaryAction={
              <IconButton onClick={() => askDeleteFile(file.path)} edge="end">
                <Delete />
              </IconButton>
            }
            disablePadding
          >
            <ListItemButton onClick={() => onSelect(file.path)}>
              <ListItemText
                primary={file.exist ? file.path : <i>{file.path}</i>}
                secondary={`[${file.type}] ${file.description}`}
              />
            </ListItemButton>
          </ListItem>
        )}
        <ListItemButton onClick={() => setCustomFileDialogOpen(true)}>
          <ListItemText
            primary="其他配置"
            secondary="输入文件路径"
          />
        </ListItemButton>
      </List>
      <Dialog open={confirmDeleteDialogOpen}>
        <DialogTitle>删除文件</DialogTitle>
        <DialogContent>
          <DialogContentText>
            确定要删除 {deleteFileName} 吗？
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDeleteDialogOpen(false)}>取消</Button>
          <Button onClick={confirmDeleteFile}>确定</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={customFileDialogOpen}>
        <DialogTitle>输入文件路径</DialogTitle>
        <DialogContent>
          <TextField
            value={customFileName}
            onChange={event => setCustomFileName(event.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCustomFileDialogOpen(false)}>取消</Button>
          <Button onClick={selectCustomFile}>确定</Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  );
}

function isDotenv(path: string) {
  if (path.endsWith(".env")) {
    return true;
  }
  const index = path.lastIndexOf("/");
  const last = index === -1 ? path : path.slice(index + 1);
  return last.startsWith(".env.");
}

export default function Config() {
  const theme = useTheme();
  const dark = theme.palette.mode === "dark";
  const [configs, setConfigs] = useState<ConfigFile[] | undefined>(undefined);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [path, setPath] = useState("");
  const [description, setDescription] = useState("");
  const [editorValue, setEditorValue] = useState("");
  const [editorExtensions, setEditorExtensions] = useState<Extension[]>([]);

  const openDialog = async () => {
    try {
      const response = await fetch("/idhagnbot-api/configs", {
        headers: {
          Authorization: `Bearer ${sessionStorage.token}`,
        },
      });
      const result = Result.parse(await response.json());
      if (!result.success) {
        setSnackbarOpen(true);
        setSnackbarMessage(result.message);
        return;
      }
      const data = ConfigsData.parse(result.data);
      data.configs.sort((a, b) => a.path.localeCompare(b.path));
      setConfigs(data.configs);
      setDialogOpen(true);
    } catch (e) {
      setSnackbarOpen(true);
      setSnackbarMessage(String(e));
    }
  };

  const configSelected = async (fileName: string) => {
    try {
      setDialogOpen(false);
      const url = new URL("/idhagnbot-api/config", location.href);
      url.searchParams.set("name", fileName);
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${sessionStorage.token}`,
        },
      });
      const result = Result.parse(await response.json());
      if (!result.success) {
        setSnackbarOpen(true);
        setSnackbarMessage(result.message);
        return;
      }
      const data = ConfigGetData.parse(result.data);
      setPath(fileName);
      setDescription(data.schema?.description || "");
      setEditorValue(data.config);
      if (fileName.endsWith(".yaml")) {
        setEditorExtensions([yamlSchema(data.schema)]);
      } else if (fileName.endsWith(".json")) {
        setEditorExtensions([jsonSchema(data.schema)]);
      } else if (isDotenv(fileName)) {
        setEditorExtensions([StreamLanguage.define(shell)]);
      }
    } catch (e) {
      setSnackbarOpen(true);
      setSnackbarMessage(String(e));
    }
  };

  const configDelete = async (fileName: string) => {
    try {
      const url = new URL("/idhagnbot-api/config", location.href);
      url.searchParams.set("name", fileName);
      const response = await fetch(url, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${sessionStorage.token}`,
        },
      });
      const result = Result.parse(await response.json());
      if (!result.success) {
        setSnackbarOpen(true);
        setSnackbarMessage(result.message);
        return;
      }
      const data = ConfigSetDeleteData.parse(result.data);
      const response2 = await fetch("/idhagnbot-api/configs", {
        headers: {
          Authorization: `Bearer ${sessionStorage.token}`,
        },
      });
      const result2 = Result.parse(await response2.json());
      if (!result2.success) {
        setSnackbarOpen(true);
        setSnackbarMessage(result2.message);
        return;
      }
      const data2 = ConfigsData.parse(result2.data);
      data2.configs.sort((a, b) => a.path.localeCompare(b.path));
      setConfigs(data2.configs);
      setSnackbarOpen(true);
      if (data.reloaded) {
        setSnackbarMessage("已删除并重载配置");
      } else {
        setSnackbarMessage("已删除配置，当前配置不支持热重载");
      }
    } catch (e) {
      setSnackbarOpen(true);
      setSnackbarMessage(String(e));
    }
  };

  const saveConfig = async () => {
    try {
      if (!path) {
        setSnackbarOpen(true);
        setSnackbarMessage("未打开配置");
        return;
      }
      const url = new URL("/idhagnbot-api/config", location.href);
      url.searchParams.set("name", path);
      const response = await fetch(url, {
        method: "POST",
        body: JSON.stringify({
          config: editorValue
        }),
        headers: {
          Authorization: `Bearer ${sessionStorage.token}`,
        },
      });
      const result = Result.parse(await response.json());
      if (!result.success) {
        setSnackbarOpen(true);
        setSnackbarMessage(result.message);
        return;
      }
      const data = ConfigSetDeleteData.parse(result.data);
      setSnackbarOpen(true);
      if (data.reloaded) {
        setSnackbarMessage("已保存并重载配置");
      } else {
        setSnackbarMessage("已保存配置，当前配置不支持热重载");
      }
    } catch (e) {
      setSnackbarOpen(true);
      setSnackbarMessage(String(e));
    }
  };

  return (
    <DashboardContainer sx={{ height: "100vh" }}>
      <Toolbar>
        <Tooltip title="打开">
          <IconButton edge="start" onClick={openDialog}>
            <Folder />
          </IconButton>
        </Tooltip>
        <Box sx={{ flexGrow: 1, textAlign: "center" }}>
          <Tooltip title={description}>
            <span>{path || "没有打开文件"}</span>
          </Tooltip>
        </Box>
        <Tooltip title="保存并重载">
          <IconButton edge="end" onClick={saveConfig}>
            <Save />
          </IconButton>
        </Tooltip>
      </Toolbar>
      <Divider />
      <CodeMirror
        theme={dark ? "dark" : "light"}
        value={editorValue}
        onChange={value => setEditorValue(value)}
        extensions={editorExtensions}
        className={classes.editor}
      />
      <ConfigSelectDialog
        configs={configs}
        open={dialogOpen}
        onSelect={configSelected}
        onDelete={configDelete}
        onCancel={() => setDialogOpen(false)}
      />
      <Snackbar
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={() => setSnackbarOpen(false)}
        message={snackbarMessage}
      />
    </DashboardContainer>
  );
}
