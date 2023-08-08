package git

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/lguibr/comai/env"
)

func GetRepositoryName() (string, error) {
	cmd := exec.Command("git", "rev-parse", "--show-toplevel")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(out.String()), nil
}

func GetCurrentBranchName() (string, error) {
	cmd := exec.Command("git", "rev-parse", "--abbrev-ref", "HEAD")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(out.String()), nil
}

func GetStagedChangesDiff() (string, error) {
	cmd := exec.Command("git", "diff", "--staged")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return out.String(), nil
}

func StageAllChanges() error {
	cmd := exec.Command("git", "add", "--all")
	return cmd.Run()
}

func CreateCommit(commitMessage string) error {
	cmd := exec.Command("git", "commit", "-m", commitMessage)
	return cmd.Run()
}

func GetCommitTemplate() (string, error) {
	repoPath, err := GetRepositoryName()
	if err != nil {
		return "", err
	}

	// Construct the path to the repository-specific template file
	templatePath := filepath.Join(repoPath, "./.git/commit_template.txt")
	// Check if the file exists
	if _, err := os.Stat(templatePath); !os.IsNotExist(err) {
		templateBytes, err := os.ReadFile(templatePath)
		if err != nil {
			return "", err
		}
		template := string(templateBytes)
		return template, nil
	}

	// If no repository-specific template is found, return the global template
	return env.TEMPLATE_COMMIT, nil
}

func SaveCommitTemplate(template string) error {
	repoPath, err := GetRepositoryName()
	if err != nil {
		return err
	}

	// Construct the path to the hidden template file inside the .git directory
	templatePath := filepath.Join(repoPath, ".git", "commit_template.txt")

	// Write the template content to the file
	return os.WriteFile(templatePath, []byte(template), 0644)
}

func PerformGitReset(stepsBack int) error {
	cmd := exec.Command("git", "reset", fmt.Sprintf("HEAD~%d", stepsBack))
	return cmd.Run()
}
