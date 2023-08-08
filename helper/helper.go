package helper

import "fmt"

func FormatDiffWithRepoAndBranchInfo(repoName, branchName, diff string) string {
	return fmt.Sprintf("%s/%s\n\n%s", repoName, branchName, diff)
}
