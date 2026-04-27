<?php
if (isset($_GET['catch'])) {
    $catch = htmlspecialchars($_GET['catch']);
    echo "You caught: " . $catch;
} else {
    echo "No code";
}
?>
