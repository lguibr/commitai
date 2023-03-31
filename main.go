package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/urfave/cli/v2"
)

const (
	OpenAIAPIURL = "https://api.openai.com/v1/chat/completions"
)

var (
	OpenAI_API_KEY  = os.Getenv("OPENAI_API_KEY")
	TEMPLATE_COMMIT = os.Getenv("TEMPLATE_COMMIT")
)

func getRepositoryName() (string, error) {
	cmd := exec.Command("git", "rev-parse", "--show-toplevel")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return filepath.Base(strings.TrimSpace(out.String())), nil
}

func getCurrentBranchName() (string, error) {
	cmd := exec.Command("git", "rev-parse", "--abbrev-ref", "HEAD")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(out.String()), nil
}

func getStagedChangesDiff() (string, error) {
	cmd := exec.Command("git", "diff", "--staged")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return out.String(), nil
}

func formatDiffWithRepoAndBranchInfo(repoName, branchName, diff string) string {
	return fmt.Sprintf("%s/%s\n\n%s", repoName, branchName, diff)
}

func stageAllChanges() error {
	cmd := exec.Command("git", "add", "--all")
	return cmd.Run()
}

func prepareRequestPayload(diff, template string) ([]byte, error) {
	systemMessage := "You are a helpful git commit assistant, you will receive a git diff and you will generate a commit message."

	if template != "" {
		systemMessage += " This message should follow the following template: " + template
	}

	payload := map[string]interface{}{
		"model": "gpt-4",
		"messages": []map[string]string{
			{
				"role":    "system",
				"content": systemMessage,
			},
			{
				"role":    "user",
				"content": diff,
			},
		},
	}

	return json.Marshal(payload)
}

func createAPIRequest(apiKey string, payloadBytes []byte) (*http.Request, error) {
	req, err := http.NewRequest("POST", OpenAIAPIURL, bytes.NewReader(payloadBytes))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	return req, nil
}

func sendAPIRequest(req *http.Request) (*http.Response, error) {
	return http.DefaultClient.Do(req)
}

func readResponseBody(resp *http.Response) ([]byte, error) {
	return io.ReadAll(resp.Body)
}

func parseResponse(responseBody []byte) (string, error) {
	var responseData map[string]interface{}
	err := json.Unmarshal(responseBody, &responseData)
	if err != nil {
		return "", err
	}

	choices := responseData["choices"].([]interface{})
	choice := choices[0].(map[string]interface{})
	message := choice["message"].(map[string]interface{})

	return message["content"].(string), nil
}

func createCommit(commitMessage string) error {
	cmd := exec.Command("git", "commit", "-m", commitMessage)
	return cmd.Run()
}

func main() {
	app := &cli.App{
		Name:  "git-commit-helper",
		Usage: "Generate git commit messages using GPT-4",
		Flags: []cli.Flag{
			&cli.BoolFlag{
				Name:    "commit",
				Aliases: []string{"m"},
				Usage:   "Commit the changes with the generated message",
			},
			&cli.StringFlag{
				Name:    "template",
				Aliases: []string{"t"},
				Value:   TEMPLATE_COMMIT,
				Usage:   "Specify a commit message template",
			},
			&cli.BoolFlag{
				Name:    "add",
				Aliases: []string{"a"},
				Usage:   "Stage all changes before generating the commit message",
			},
		},
		Action: func(c *cli.Context) error {
			if OpenAI_API_KEY == "" {
				fmt.Println("Error: OPENAI_API_KEY environment variable not set")
				os.Exit(1)
			}

			if c.Bool("add") {
				err := stageAllChanges()
				if err != nil {
					fmt.Println("Error: Failed to stage all changes")
					os.Exit(1)
				}
			}

			diff, err := getStagedChangesDiff()
			if err != nil {
				fmt.Println("Error: Failed to get staged diff")
				os.Exit(1)
			}

			if diff == "" {
				fmt.Println("Warning: No staged changes found. Exiting.")
				os.Exit(0)
			}

			repoName, err := getRepositoryName()
			if err != nil {
				fmt.Println("Error: Failed to get repository name")
				os.Exit(1)
			}

			branchName, err := getCurrentBranchName()
			if err != nil {
				fmt.Println("Error: Failed to get current branch name")
				os.Exit(1)
			}

			formattedDiff := formatDiffWithRepoAndBranchInfo(repoName, branchName, diff)

			template := c.String("template")
			payloadBytes, err := prepareRequestPayload(formattedDiff, template)
			if err != nil {
				fmt.Println("Error: Failed to prepare request payload")
				os.Exit(1)
			}

			req, err := createAPIRequest(OpenAI_API_KEY, payloadBytes)
			if err != nil {
				fmt.Println("Error: Failed to create API request")
				os.Exit(1)
			}

			resp, err := sendAPIRequest(req)
			if err != nil {
				fmt.Println("Error: Failed to send API request")
				os.Exit(1)
			}
			defer resp.Body.Close()

			if resp.StatusCode != http.StatusOK {
				fmt.Println("Error: Failed to generate commit message using open_ai api")
				os.Exit(1)
			}

			responseBody, err := readResponseBody(resp)
			if err != nil {
				fmt.Println("Error: Failed to read response body")
				os.Exit(1)
			}

			commitMessage, err := parseResponse(responseBody)
			if err != nil {
				fmt.Println("Error: Failed to parse response")
				os.Exit(1)
			}

			if c.Bool("commit") {
				err := createCommit(commitMessage)
				if err != nil {
					fmt.Println("Error: Failed to create commit")
					os.Exit(1)
				}
				fmt.Printf("Committed message: \n\n %s\n", commitMessage)
			} else {
				fmt.Printf("Generated commit message: \n\n %s\n", commitMessage)
			}

			return nil
		},
	}

	err := app.Run(os.Args)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
