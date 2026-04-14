package auth

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// DeviceCodeResponse is the backend's response to POST /auth/device-code.
type DeviceCodeResponse struct {
	DeviceCode string `json:"device_code"`
	LoginURL   string `json:"login_url"`
	ExpiresIn  int    `json:"expires_in"`
}

// PollResponse is the backend's response to GET /auth/poll.
type PollResponse struct {
	Status      string `json:"status"`       // "pending" or "approved"
	AccessToken string `json:"access_token"` // set when status == "approved"
}

// httpClient is a shared client with a sane timeout so a hung backend
// doesn't stall the login flow indefinitely.
var httpClient = &http.Client{Timeout: 15 * time.Second}

// LoginWithDeviceCode performs the device authorization flow:
//  1. Request a device code from the backend
//  2. Open the login page in the browser with the device code
//  3. Poll the backend until the user approves or timeout
//
// Returns the access token on success.
func LoginWithDeviceCode(backendURL string) (string, error) {
	// Step 1: Request device code
	reqCtx, reqCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer reqCancel()
	req, err := http.NewRequestWithContext(
		reqCtx, "POST",
		backendURL+"/api/v1/desktop-client/auth/device-code",
		bytes.NewReader(nil),
	)
	if err != nil {
		return "", fmt.Errorf("build device code request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("request device code: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return "", fmt.Errorf("device code request failed (%d): %s", resp.StatusCode, string(body))
	}

	var dcResp DeviceCodeResponse
	if err := json.Unmarshal(body, &dcResp); err != nil {
		return "", fmt.Errorf("parse device code: %w", err)
	}

	// Step 2: Open browser to frontend login page (URL provided by backend)
	openBrowser(dcResp.LoginURL)

	// Step 3: Poll for approval
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(dcResp.ExpiresIn)*time.Second)
	defer cancel()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return "", fmt.Errorf("login timed out")
		case <-ticker.C:
			token, done, err := pollDeviceCode(ctx, backendURL, dcResp.DeviceCode)
			if err != nil {
				return "", err
			}
			if done {
				return token, nil
			}
		}
	}
}

func pollDeviceCode(ctx context.Context, backendURL, code string) (token string, done bool, err error) {
	req, err := http.NewRequestWithContext(
		ctx, "GET",
		backendURL+"/api/v1/desktop-client/auth/poll?code="+code,
		nil,
	)
	if err != nil {
		return "", false, fmt.Errorf("build poll request: %w", err)
	}

	resp, err := httpClient.Do(req)
	if err != nil {
		return "", false, fmt.Errorf("poll: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 404 {
		return "", false, fmt.Errorf("device code expired or not found")
	}
	if resp.StatusCode != 200 {
		return "", false, fmt.Errorf("poll failed (%d): %s", resp.StatusCode, string(body))
	}

	var pollResp PollResponse
	if err := json.Unmarshal(body, &pollResp); err != nil {
		return "", false, fmt.Errorf("parse poll response: %w", err)
	}

	if pollResp.Status == "approved" && pollResp.AccessToken != "" {
		return pollResp.AccessToken, true, nil
	}

	return "", false, nil
}
