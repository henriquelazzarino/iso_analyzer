package com.example.demo;

public class Logger {
    public void warn(String msg) {
        System.err.println("[WARN] " + msg);
    }
    public void info(String msg) {
        System.out.println("[INFO] " + msg);
    }
}
