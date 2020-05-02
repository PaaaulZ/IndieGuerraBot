<?php require_once('settings.php'); ?>
<?php header('Content-Type: text/html; charset=utf-8'); ?>
<HTML>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <meta name="og:title" property="og:title" content="IndieGuerraBot by PaaaulZ | What if Italian indie artists could fight to conquer Italy?">
        <meta name="description" content="IndieGuerraBot by PaaaulZ | What if Italian indie artists could fight to conquer Italy?" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
        <title>IndieGuerraBot by PaaaulZ | What if Italian indie artists could fight to conquer Italy?</title>
    </head>
    <body>
        <?php 
            // -3 to ignore ., .. and index.htm (prevent directory listing)
            $runsCount = count(scandir(RUNS_BASE_PATH)) - 3;
        ?>
        <table rows = <?php echo((intval($runsCount / 3))+1) ?> cols = 3>
        <?php
            /*
                * A folder for every run
                * -2 to ignore '.' and '..'
                * First run is 0 (empty map)!
            */
            echo('<tr>');
            for ($i = 0; $i < $runsCount; $i++)
            {
                $runPath = RUNS_BASE_PATH . $i;
                if (!file_exists("$runPath/map.png") || !file_exists("$runPath/differences.log"))
                {
                    echo("<font color = 'red'>Missing data for run $i, skipping!</font><br/>");
                    continue;
                }
                $runDate = date ("d/m/Y", filemtime($runPath));
                echo("<a href = 'javascript:window.open(\"getRun.php?run_id=$i\",\"_blank\")'>Run $i ($runDate)</a><br/>");
            }
        ?>


        </table>
    </body>
</HTML>