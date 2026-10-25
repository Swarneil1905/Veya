//! Fixed loopback HTTP transport, never a URL supplied by web content.
use serde_json::Value;
use std::io::{Read, Write};
use std::net::{Ipv4Addr, SocketAddr, TcpStream};
use std::time::{Duration, Instant};

pub fn request(
    port: u16,
    token: &str,
    method: &str,
    path: &str,
    body: &Value,
) -> Result<Value, String> {
    let bytes = if method == "POST" {
        serde_json::to_vec(body).map_err(|_| "invalid_input")?
    } else {
        Vec::new()
    };
    if bytes.len() > 786_432 {
        return Err("too_large".into());
    }
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let mut socket = TcpStream::connect_timeout(&address, Duration::from_secs(2))
        .map_err(|_| "runtime_unreachable")?;
    socket
        .set_read_timeout(Some(Duration::from_secs(10)))
        .map_err(|_| "transport_failed")?;
    socket
        .set_write_timeout(Some(Duration::from_secs(10)))
        .map_err(|_| "transport_failed")?;
    write!(socket, "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {token}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n", bytes.len()).map_err(|_| "transport_failed")?;
    socket.write_all(&bytes).map_err(|_| "transport_failed")?;
    let deadline = Instant::now() + Duration::from_secs(12);
    let mut response = Vec::new();
    let mut chunk = [0; 8192];
    loop {
        if Instant::now() >= deadline {
            return Err("runtime_timeout".into());
        }
        let size = socket.read(&mut chunk).map_err(|_| "runtime_timeout")?;
        if size == 0 {
            break;
        }
        response.extend_from_slice(&chunk[..size]);
        if response.len() > 2_097_152 {
            return Err("too_large".into());
        }
    }
    decode(&response)
}

fn decode(response: &[u8]) -> Result<Value, String> {
    let split = response
        .windows(4)
        .position(|s| s == b"\r\n\r\n")
        .ok_or("invalid_response")?;
    let headers = std::str::from_utf8(&response[..split]).map_err(|_| "invalid_response")?;
    let status = headers
        .lines()
        .next()
        .and_then(|s| s.split_whitespace().nth(1))
        .ok_or("invalid_response")?;
    let body = &response[split + 4..];
    // The supported JSON endpoints emit Content-Length; do not implement a second streaming protocol.
    let length = headers
        .lines()
        .find_map(|line| {
            let (key, value) = line.split_once(':')?;
            if key.eq_ignore_ascii_case("content-length") {
                value.trim().parse::<usize>().ok()
            } else {
                None
            }
        })
        .ok_or("invalid_response")?;
    if length != body.len() {
        return Err("invalid_response".into());
    }
    let value: Value = serde_json::from_slice(body).map_err(|_| "invalid_response")?;
    if status == "200" || status == "201" {
        return Ok(value);
    }
    let code = value
        .pointer("/error/code")
        .and_then(Value::as_str)
        .unwrap_or("request_failed");
    let safe = match code {
        "unauthenticated" | "forbidden" | "conflict" | "invalid_input" | "not_found" | "busy"
        | "recovery_required" | "invalid_cursor" => code,
        _ => "request_failed",
    };
    Err(safe.into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_truncation_and_redirects_and_does_not_echo_error_content() {
        assert!(decode(b"HTTP/1.1 200 OK\r\nContent-Length: 9\r\n\r\n{}").is_err());
        assert!(decode(b"HTTP/1.1 302 Found\r\nContent-Length: 2\r\n\r\n{}").is_err());
        let body = r#"{"error":{"code":"secret-sentinel"}}"#;
        let response = format!(
            "HTTP/1.1 500 Error\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        );
        assert_eq!(decode(response.as_bytes()).unwrap_err(), "request_failed");
    }
}
