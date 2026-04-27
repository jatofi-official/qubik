<?php
if (isset($_GET['id'])) {
    $catch = htmlspecialchars($_GET['id']);
    echo "You caught: " . $catch;
} else {
    echo "No code";
}
?>
