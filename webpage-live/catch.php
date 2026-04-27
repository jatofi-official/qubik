<?php
if (isset($_GET['id'])) {
    $catch = htmlspecialchars($_GET['catch']);
    echo "You caught: " . $catch;
} else {
    echo "No code";
}
?>
