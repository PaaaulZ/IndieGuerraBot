<HTML>
    <meta charset="utf-8">
    <head>
<?php
require_once('settings.php');
$runsCount = count(scandir(RUNS_BASE_PATH)) - 2;
$runID = intval($_GET['run_id']);
if ($runID > $runsCount || !is_numeric($runID))
{
    /*
        Somebody messed with the ID?.
        Return 404 and stop execution.
    */

    http_response_code(404);
    die('Invalid run ID');
}

$runPath = RUNS_BASE_PATH . $runID;
$imagePath = RUNS_BASE_PATH . $runID . "/map.png";
$differencesPath = RUNS_BASE_PATH . $runID . "/differences.log";
$differencesText = @file_get_contents_utf8($differencesPath);
$runDate = date ("d/m/Y", filemtime($runPath));
// If differences.log is empty we have no changes since the previous run.
$differencesText = empty($differencesText) ? NO_CHANGES_MSG : str_replace("\n",'<br/>',$differencesText);
?>
        <title>IndieGuerraBot by PaaaulZ | Run <?php echo("$runID ($runDate)"); ?></title>
    </head>
    <body>
        <img src = '<?php echo($imagePath); ?>' width = <?php echo(MAP_SIZE_WIDTH); ?> height = <?php echo(MAP_SIZE_HEIGHT); ?>/><br/><br/>
        <p><?php echo($differencesText) ?></p></td>
    </body>
</HTML>
<?php
function file_get_contents_utf8($fn) 
{
    // Thanks to: https://stackoverflow.com/questions/2236668/file-get-contents-breaks-up-utf-8-characters
    $content = file_get_contents($fn);
    return mb_convert_encoding($content, 'UTF-8',mb_detect_encoding($content, 'UTF-8, ISO-8859-1', true));
}
?>