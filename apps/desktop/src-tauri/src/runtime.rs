//! One owned child, serialized lifecycle changes, no credentials exposed to React.
use serde::Serialize;
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

use crate::transport;

#[derive(Clone, Serialize)]
pub struct Health {
    pub state: String,
    pub message: String,
}

pub struct Runtime {
    child: Option<Child>,
    port: u16,
    token: String,
    python: PathBuf,
    source: PathBuf,
    workspace: PathBuf,
    log: PathBuf,
    health: Health,
}

impl Runtime {
    pub fn new(python: PathBuf, source: PathBuf, workspace: PathBuf, log: PathBuf) -> Self {
        Self {
            child: None,
            port: 0,
            token: String::new(),
            python,
            source,
            workspace,
            log,
            health: Health {
                state: "stopped".into(),
                message: "Runtime is stopped.".into(),
            },
        }
    }

    fn report(&mut self, state: &str, message: &str) -> Health {
        self.health = Health {
            state: state.into(),
            message: message.into(),
        };
        if let Some(parent) = self.log.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        // Fixed diagnostic strings only, never credentials, instructions or server payloads.
        use std::fs::OpenOptions;
        if std::fs::metadata(&self.log).is_ok_and(|m| m.len() > 65_536) {
            let _ = std::fs::write(&self.log, "");
        }
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(&self.log) {
            let _ = writeln!(file, "{state}: {message}");
        }
        self.health.clone()
    }

    pub fn health(&mut self) -> Health {
        if let Some(child) = &mut self.child {
            if !matches!(child.try_wait(), Ok(None)) {
                self.child = None;
                self.token.clear();
                self.port = 0;
                return self.report(
                    "failed",
                    "Runtime stopped unexpectedly. Restart to reconnect to saved work.",
                );
            }
        }
        self.health.clone()
    }

    pub fn start(&mut self) -> Health {
        if self.health().state == "ready" {
            return self.health.clone();
        }
        self.stop();
        if !self.source.join("veya/desktop.py").is_file() {
            return self.report(
                "failed",
                "Runtime files are missing. Repair the Veya installation.",
            );
        }
        let mut random = [0u8; 32];
        if getrandom::getrandom(&mut random).is_err() {
            return self.report("failed", "Session credential could not be created.");
        }
        self.token = random.iter().map(|b| format!("{b:02x}")).collect();
        let mut command = Command::new(&self.python);
        command
            .args(["-u", "-m", "veya.desktop"])
            .current_dir(&self.source)
            .env("PYTHONPATH", &self.source)
            .env("PYTHONUTF8", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW for the owned helper only.
        }
        let mut child = match command.spawn() { Ok(child) => child, Err(_) => return self.report("failed", "Python could not start. Configure VEYA_PYTHON with a supported Python environment.") };
        let input =
            json!({"protocol": 1, "storage_root": self.workspace, "session_token": self.token});
        let sent = child
            .stdin
            .as_mut()
            .is_some_and(|stdin| writeln!(stdin, "{input}").is_ok());
        if !sent {
            let _ = child.kill();
            let _ = child.wait();
            return self.report("failed", "Runtime bootstrap failed.");
        }
        let stdout = match child.stdout.take() {
            Some(out) => out,
            None => {
                let _ = child.kill();
                let _ = child.wait();
                return self.report("failed", "Runtime pipe failed.");
            }
        };
        let (send, receive) = mpsc::sync_channel(1);
        std::thread::spawn(move || {
            let mut line = String::new();
            let _ = BufReader::new(stdout.take(4096)).read_line(&mut line);
            let _ = send.send(line);
        });
        self.child = Some(child);
        let ready = receive
            .recv_timeout(Duration::from_secs(12))
            .ok()
            .and_then(|s| serde_json::from_str::<Value>(&s).ok());
        let port = ready
            .as_ref()
            .and_then(|v| v["port"].as_u64())
            .filter(|p| *p > 0 && *p <= 65535);
        if ready
            .as_ref()
            .is_none_or(|v| v["status"] != "ready" || v["protocol"] != 1)
            || port.is_none()
        {
            self.stop();
            return self.report("failed", "Runtime readiness failed. Check Python dependencies and runtime version, then restart.");
        }
        self.port = port.unwrap_or(0) as u16;
        match transport::request(self.port, &self.token, "GET", "/v1/health", &Value::Null) {
            Ok(value) if value["protocol"] == 1 => {
                self.report("ready", "Connected to your local workspace.")
            }
            _ => {
                self.stop();
                self.report("failed", "Runtime version or authentication check failed.")
            }
        }
    }

    pub fn restart(&mut self) -> Health {
        self.stop();
        self.start()
    }

    pub fn stop(&mut self) {
        if let Some(mut child) = self.child.take() {
            drop(child.stdin.take()); // EOF requests bounded graceful shutdown.
            let deadline = Instant::now() + Duration::from_secs(4);
            loop {
                match child.try_wait() {
                    Ok(Some(_)) => {
                        self.report("stopped", "Runtime stopped; saved work retained.");
                        break;
                    }
                    _ if Instant::now() >= deadline => {
                        let _ = child.kill();
                        let _ = child.wait();
                        self.report("stopped", "Runtime shutdown timed out; owned process terminated. Saved work retained.");
                        break;
                    }
                    _ => std::thread::sleep(Duration::from_millis(40)),
                }
            }
        }
        self.token.clear();
        self.port = 0;
    }

    pub fn call(&mut self, operation: &str, args: Value) -> Result<Value, String> {
        let (method, path, body) = route(operation, args)?;
        if self.health().state != "ready" {
            return Err("runtime_unavailable".into());
        }
        transport::request(self.port, &self.token, method, &path, &body)
    }
}
impl Drop for Runtime {
    fn drop(&mut self) {
        self.stop();
    }
}

fn id(value: &Value) -> Result<&str, String> {
    let value = value.as_str().ok_or("invalid_input")?;
    if value.is_empty()
        || value.len() > 64
        || !value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
    {
        return Err("invalid_input".into());
    }
    Ok(value)
}

fn route(operation: &str, args: Value) -> Result<(&'static str, String, Value), String> {
    let object = args.as_object().ok_or("invalid_input")?;
    let allowed: &[&str] = match operation {
        "list_tasks" | "recovery" => &[],
        "submit_task" => &["client_request_id", "title", "instruction"],
        "latest_run" => &["task_id"],
        "events" => &["run_id", "after"],
        _ => return Err("forbidden".into()),
    };
    if object.keys().any(|key| !allowed.contains(&key.as_str())) {
        return Err("invalid_input".into());
    }
    let path = match operation {
        "list_tasks" => "/v1/tasks?limit=10".into(),
        "recovery" => "/v1/workspace/recovery".into(),
        "submit_task" => {
            id(&args["client_request_id"])?;
            for (key, max) in [("title", 200), ("instruction", 20_000)] {
                let text = args[key].as_str().ok_or("invalid_input")?;
                if text.trim().is_empty() || text.chars().count() > max {
                    return Err("invalid_input".into());
                }
            }
            return Ok(("POST", "/v1/tasks".into(), args));
        }
        "latest_run" => format!("/v1/tasks/{}/latest-run", id(&args["task_id"])?),
        "events" => {
            let run = id(&args["run_id"])?;
            let mut path = format!("/v1/runs/{run}/event-page");
            if !args["after"].is_null() {
                let cursor = args["after"].as_str().ok_or("invalid_input")?;
                let (name, number) = cursor.split_once(':').ok_or("invalid_input")?;
                if name != run
                    || number.is_empty()
                    || number.len() > 18
                    || !number.bytes().all(|b| b.is_ascii_digit())
                {
                    return Err("invalid_input".into());
                }
                path.push_str(&format!("?after={name}%3A{number}"));
            }
            path
        }
        _ => return Err("forbidden".into()),
    };
    Ok(("GET", path, Value::Null))
}

pub fn runtime_source(resource_dir: &Path) -> PathBuf {
    let packaged = resource_dir.join("runtime");
    if packaged.join("veya/desktop.py").is_file() {
        return packaged;
    }
    #[cfg(debug_assertions)]
    {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../services/runtime")
    }
    #[cfg(not(debug_assertions))]
    {
        packaged
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn test_root() -> PathBuf {
        let mut bytes = [0u8; 8];
        getrandom::getrandom(&mut bytes).unwrap();
        let suffix: String = bytes.iter().map(|b| format!("{b:02x}")).collect();
        let root = std::env::temp_dir().join(format!("veya-host-test-{suffix}"));
        std::fs::create_dir_all(&root).unwrap();
        root
    }
    #[test]
    fn owned_runtime_reuses_one_child_reconnects_and_preserves_tasks() {
        let root = test_root();
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../services/runtime");
        let mut host = Runtime::new(
            "python".into(),
            source,
            root.join("workspace"),
            root.join("runtime.log"),
        );
        assert_eq!(host.start().state, "ready");
        let first = host.child.as_ref().unwrap().id();
        assert_eq!(host.start().state, "ready");
        assert_eq!(host.child.as_ref().unwrap().id(), first);
        let request = json!({"client_request_id":"native_test", "title":"Native task", "instruction":"Preserve across restart"});
        let saved = host.call("submit_task", request.clone()).unwrap();
        let token = host.token.clone();
        assert_eq!(host.restart().state, "ready");
        assert_ne!(host.token, token);
        assert_eq!(
            host.call("submit_task", request).unwrap()["task"]["id"],
            saved["task"]["id"]
        );
        assert_eq!(
            host.call("list_tasks", json!({})).unwrap()["items"]
                .as_array()
                .unwrap()
                .len(),
            1
        );
        host.child.as_mut().unwrap().kill().unwrap();
        host.child.as_mut().unwrap().wait().unwrap();
        assert_eq!(host.health().state, "failed");
        assert_eq!(host.start().state, "ready");
        host.stop();
        assert!(host.child.is_none());
        assert!(!std::fs::read_to_string(root.join("runtime.log"))
            .unwrap()
            .contains(&token));
        drop(host);
        std::fs::remove_dir_all(root).unwrap(); // Exact newly-created test directory only.
    }
    #[test]
    fn mismatch_and_hung_child_are_reaped_with_diagnostics() {
        let root = test_root();
        let package = root.join("source/veya");
        std::fs::create_dir_all(&package).unwrap();
        std::fs::write(package.join("__init__.py"), "").unwrap();
        std::fs::write(package.join("desktop.py"), "import sys,time\nsys.stdin.readline()\nprint('{\"status\":\"ready\",\"protocol\":2,\"port\":12345}',flush=True)\ntime.sleep(60)\n").unwrap();
        let mut host = Runtime::new(
            "python".into(),
            root.join("source"),
            root.join("workspace"),
            root.join("runtime.log"),
        );
        let started = Instant::now();
        assert_eq!(host.start().state, "failed");
        assert!(started.elapsed() < Duration::from_secs(10));
        assert!(host.child.is_none());
        assert!(std::fs::read_to_string(root.join("runtime.log"))
            .unwrap()
            .contains("owned process terminated"));
        drop(host);
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn missing_python_is_recoverable_and_creates_no_child() {
        let root = test_root();
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../services/runtime");
        let mut host = Runtime::new(
            root.join("missing-python.exe"),
            source,
            root.join("workspace"),
            root.join("runtime.log"),
        );
        assert_eq!(host.start().state, "failed");
        assert!(host.child.is_none());
        drop(host);
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn content_cannot_request_arbitrary_native_or_http_access() {
        for operation in ["shell", "read_file", "http", "approve", "execute"] {
            assert!(route(operation, json!({})).is_err());
        }
        assert!(route("latest_run", json!({"task_id":"../../secrets"})).is_err());
        assert!(route("list_tasks", json!({"url":"https://evil.invalid"})).is_err());
        assert!(route("events", json!({"run_id":"run_a","after":"run_b:1"})).is_err());
        assert!(route(
            "events",
            json!({"run_id":"run_a","after":"run_a:1\r\nX: y"})
        )
        .is_err());
        assert_eq!(
            route("events", json!({"run_id":"run_a","after":"run_a:2"}))
                .unwrap()
                .1,
            "/v1/runs/run_a/event-page?after=run_a%3A2"
        );
    }
}
