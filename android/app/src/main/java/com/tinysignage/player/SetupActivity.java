package com.tinysignage.player;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;

/**
 * First-run setup screen. User enters their TinySignage server URL,
 * we validate it via GET /health, and store it in SharedPreferences.
 * If a valid URL is already saved, we skip straight to MainActivity.
 */
public class SetupActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "tinysignage";
    private static final String KEY_SERVER_URL = "server_url";
    private static final int CONNECT_TIMEOUT_MS = 8000;
    private static final int READ_TIMEOUT_MS = 8000;

    private EditText serverUrlInput;
    private Button connectButton;
    private TextView errorText;
    private ProgressBar progressBar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // If we already have a valid server URL, skip setup
        String savedUrl = getServerUrl();
        if (savedUrl != null && !savedUrl.isEmpty()) {
            launchPlayer();
            return;
        }

        setContentView(R.layout.activity_setup);

        serverUrlInput = findViewById(R.id.serverUrlInput);
        connectButton = findViewById(R.id.connectButton);
        errorText = findViewById(R.id.errorText);
        progressBar = findViewById(R.id.progressBar);

        connectButton.setOnClickListener(v -> onConnectClicked());

        serverUrlInput.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_DONE) {
                onConnectClicked();
                return true;
            }
            return false;
        });
    }

    private void onConnectClicked() {
        String url = serverUrlInput.getText().toString().trim();

        // Strip trailing slash
        while (url.endsWith("/")) {
            url = url.substring(0, url.length() - 1);
        }

        if (url.isEmpty()) {
            showError(getString(R.string.error_empty_url));
            return;
        }

        // Auto-prepend http:// if no scheme given
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "http://" + url;
            serverUrlInput.setText(url);
        }

        // Basic URL validation
        try {
            new URL(url);
        } catch (MalformedURLException e) {
            showError(getString(R.string.error_invalid_url));
            return;
        }

        validateServer(url);
    }

    private void validateServer(String baseUrl) {
        setLoading(true);
        hideError();

        String healthUrl = baseUrl + "/health";

        new Thread(() -> {
            try {
                HttpURLConnection conn = (HttpURLConnection) new URL(healthUrl).openConnection();
                conn.setConnectTimeout(CONNECT_TIMEOUT_MS);
                conn.setReadTimeout(READ_TIMEOUT_MS);
                conn.setRequestMethod("GET");

                int code = conn.getResponseCode();
                conn.disconnect();

                if (code == 200) {
                    // Success — save URL and launch player
                    saveServerUrl(baseUrl);
                    runOnUiThread(this::launchPlayer);
                } else {
                    runOnUiThread(() -> {
                        setLoading(false);
                        showError(getString(R.string.error_not_tinysignage));
                    });
                }
            } catch (IOException e) {
                runOnUiThread(() -> {
                    setLoading(false);
                    showError(getString(R.string.error_connection_failed));
                });
            }
        }).start();
    }

    private void setLoading(boolean loading) {
        connectButton.setEnabled(!loading);
        serverUrlInput.setEnabled(!loading);
        progressBar.setVisibility(loading ? View.VISIBLE : View.GONE);
        if (loading) {
            connectButton.setText(R.string.validating);
        } else {
            connectButton.setText(R.string.connect_button);
        }
    }

    private void showError(String message) {
        errorText.setText(message);
        errorText.setVisibility(View.VISIBLE);
    }

    private void hideError() {
        errorText.setVisibility(View.GONE);
    }

    private void launchPlayer() {
        Intent intent = new Intent(this, MainActivity.class);
        startActivity(intent);
        finish();
    }

    private String getServerUrl() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        return prefs.getString(KEY_SERVER_URL, null);
    }

    private void saveServerUrl(String url) {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit().putString(KEY_SERVER_URL, url).apply();
    }
}
