import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

IMG_PH = (
    '<div class="img-placeholder" style="background:#e8f4f7;border:2px dashed #2d8fa5;'
    'border-radius:8px;padding:40px;text-align:center;color:#2d8fa5;margin:1rem 0;">'
    '&#128247; Image coming soon &mdash; upload via Admin &rarr; Edit &rarr; Image button'
    '</div>'
)

VID_PH = (
    '<div class="video-placeholder" style="background:#0f1728;border:2px dashed #f5a623;'
    'border-radius:8px;padding:60px;text-align:center;color:#f5a623;margin:1rem 0;">'
    '&#127916; Video coming soon &mdash; paste YouTube/Vimeo embed code here via Admin &rarr; Edit'
    '</div>'
)


class Command(BaseCommand):
    help = 'Seed initial public website content (idempotent — safe to run twice)'

    def handle(self, *args, **options):
        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).first()
        self._seed_static_pages()
        self._seed_news(admin_user)
        self._seed_announcements()
        self._seed_gallery()
        self.stdout.write(self.style.SUCCESS('Public website content seeded successfully.'))

    def _seed_static_pages(self):
        from public.models import StaticPage
        pages = [
            {
                'slug': 'general-rules',
                'title': 'General Rules',
                'nav_section': 'contest',
                'nav_order': 1,
                'body': (
                    '<h2>General Rules</h2>'
                    '<p>RoboSTEAM competitions follow a set of general rules designed to ensure fair play, safety, and an educational experience for all participants.</p>'
                    '<h3>Eligibility</h3>'
                    '<p>Competitions are open to student teams from schools and vocational education institutions participating in the ROBO STEAM ACADEMY Erasmus+ project (KA220-VET-7CF4F308).</p>'
                    '<h3>Team Composition</h3>'
                    '<p>Each team consists of 2&ndash;4 students supervised by a teacher or mentor. Teams must register through their local organiser.</p>'
                    '<h3>Robot Requirements</h3>'
                    '<ul><li>Maximum dimensions: 30cm &times; 30cm &times; 30cm</li>'
                    '<li>Maximum weight: 2kg</li>'
                    '<li>Must use a Raspberry Pi Pico W or compatible microcontroller</li>'
                    '<li>No external communication during a run (except competition server commands)</li></ul>'
                    + IMG_PH +
                    '<h3>Scoring</h3>'
                    '<ul><li><strong>Timed categories</strong> (e.g., Line Following): lowest time wins. Penalties are added for infractions.</li>'
                    '<li><strong>Judged categories</strong> (e.g., Object Manipulation): judges award a score from 1&ndash;100.</li></ul>'
                    '<h3>Safety and Fair Play</h3>'
                    '<p>Robots that damage the arena or pose a safety risk will be disqualified. Unsportsmanlike conduct results in immediate disqualification.</p>'
                ),
            },
            {
                'slug': 'participate',
                'title': 'How to Participate',
                'nav_section': 'participate',
                'nav_order': 1,
                'body': (
                    '<h2>How to Participate</h2>'
                    '<p>RoboSTEAM competitions are open to student teams from partner schools across Bulgaria, Slovakia, and Romania.</p>'
                    '<h3>Step 1: Find your local organiser</h3>'
                    '<p>Contact the RoboSTEAM coordinator at your school. They will register your school and provide access to the competition platform.</p>'
                    '<h3>Step 2: Form a team</h3>'
                    '<p>Gather 2&ndash;4 students interested in robotics or programming.</p>'
                    '<h3>Step 3: Build your robot</h3>'
                    '<p>Follow the <a href="/pages/how-to-build-robot/">How to Build a Robot</a> guide.</p>'
                    + IMG_PH +
                    '<h3>Step 4: Register and compete!</h3>'
                    '<p>Your organiser will provide a registration link when a competition is announced.</p>'
                ),
            },
            {
                'slug': 'how-to-build-robot',
                'title': 'How to Build a Robot',
                'nav_section': 'participate',
                'nav_order': 2,
                'body': (
                    '<h2>How to Build a Robot</h2>'
                    '<p>This guide walks you through building a competition-ready robot using the Raspberry Pi Pico W and the RoboSTEAM competition library.</p>'
                    '<h3>Hardware you will need</h3>'
                    '<ul><li>Raspberry Pi Pico W or Pico W2</li>'
                    '<li>Robot chassis (2WD or 4WD kit)</li>'
                    '<li>Motor driver board (L298N or similar)</li>'
                    '<li>IR line sensor (for line following)</li>'
                    '<li>Battery pack (4&times; AA or 3.7V LiPo)</li></ul>'
                    + IMG_PH +
                    '<h3>Software setup</h3>'
                    '<p>Download our open-source competition library:<br>'
                    '<a href="https://github.com/robosteamdev/picobot-setup" target="_blank">github.com/robosteamdev/picobot-setup</a></p>'
                    + VID_PH
                ),
            },
            {
                'slug': 'what-is-a-competition',
                'title': 'What is a Competition',
                'nav_section': 'participate',
                'nav_order': 3,
                'body': (
                    '<h2>What is a RoboSTEAM Competition?</h2>'
                    '<p>A RoboSTEAM competition is an educational event where student teams test their robots in structured challenges combining engineering, programming, and teamwork.</p>'
                    + IMG_PH +
                    '<h3>How a competition day works</h3>'
                    '<ol><li><strong>Registration</strong> &mdash; Teams check in and receive their starting slot.</li>'
                    '<li><strong>Technical inspection</strong> &mdash; Judges verify robot compliance.</li>'
                    '<li><strong>Practice rounds</strong> &mdash; Teams test on the competition track.</li>'
                    '<li><strong>Qualifying rounds</strong> &mdash; Each team completes their allocated runs.</li>'
                    '<li><strong>Results and awards</strong> &mdash; Scores published on the live scoreboard.</li></ol>'
                    '<h3>Categories</h3>'
                    '<ul><li><strong>Line Following</strong> &mdash; Fastest time on the track wins.</li>'
                    '<li><strong>Autonomous Task</strong> &mdash; Timed challenge without human control.</li>'
                    '<li><strong>Object Manipulation</strong> &mdash; Judged on accuracy and technique.</li>'
                    '<li><strong>Master Control</strong> &mdash; Remote-operated, judged on precision.</li></ul>'
                    + IMG_PH
                ),
            },
            {
                'slug': 'call-for-participation',
                'title': 'Call for Participation',
                'nav_section': 'participate',
                'nav_order': 4,
                'body': (
                    '<h2>Call for Participation</h2>'
                    '<p>We invite schools and vocational education institutions from Bulgaria, Slovakia, and Romania to join the ROBO STEAM ACADEMY competition programme.</p>'
                    '<h3>Why participate?</h3>'
                    '<ul><li>Develop real engineering and programming skills</li>'
                    '<li>Experience international competition and teamwork</li>'
                    '<li>Win recognition and awards</li>'
                    '<li>Access free training materials and the open-source PicoBot library</li></ul>'
                    + IMG_PH +
                    '<p>See the <a href="/pages/register/">Registration page</a> for how to sign up.</p>'
                ),
            },
            {
                'slug': 'register',
                'title': 'Register',
                'nav_section': 'participate',
                'nav_order': 5,
                'body': (
                    '<h2>Register Your Team</h2>'
                    '<p>Team registration is managed by your local organiser. Steps:</p>'
                    '<ol><li>Contact your local organiser (teacher or school coordinator).</li>'
                    '<li>Your organiser registers your school and receives login credentials.</li>'
                    '<li>Once registered, your team appears in the competition system.</li></ol>'
                    '<p><strong>No local organiser yet?</strong> Contact the RoboSTEAM project team through Erasmus+ project channels.</p>'
                ),
            },
            {
                'slug': 'organize',
                'title': 'How to Organize',
                'nav_section': 'organize',
                'nav_order': 1,
                'body': (
                    '<h2>How to Organize a RoboSTEAM Competition</h2>'
                    '<p>This guide is for teachers, trainers, and school coordinators who want to host a competition event.</p>'
                    '<h3>Requirements</h3>'
                    '<ul><li>A venue with space for competition tracks and team tables</li>'
                    '<li>WiFi with access to the competition server</li>'
                    '<li>At least one lap timer device (NodeMCU + E18 IR sensor) for timed categories</li>'
                    '<li>A laptop or tablet for the judge interface</li></ul>'
                    + IMG_PH +
                    '<h3>Setting up the competition</h3>'
                    '<ol><li>Log into the Competition Platform as an organiser.</li>'
                    '<li>Create a new Contest and add Categories.</li>'
                    '<li>Register participating teams.</li>'
                    '<li>Assign a lap timer device to timed categories.</li>'
                    '<li>Set the competition to RUNNING when ready.</li></ol>'
                    '<p>See the <a href="/pages/judge-guide/">Judge Guide</a> for step-by-step operating instructions.</p>'
                ),
            },
            {
                'slug': 'competition-and-organization',
                'title': 'Competition & Organization',
                'nav_section': 'organize',
                'nav_order': 2,
                'body': (
                    '<h2>Competition &amp; Organization</h2>'
                    '<p>The ROBO STEAM ACADEMY competition framework is designed to be easy to set up while providing a professional competition experience.</p>'
                    '<h3>Competition structure</h3>'
                    '<ul><li><strong>Contest</strong> &mdash; The overall event (e.g., "RoboSTEAM Spring Cup 2027")</li>'
                    '<li><strong>Categories</strong> &mdash; Disciplines within the contest (e.g., Line Following)</li>'
                    '<li><strong>Runs</strong> &mdash; Individual attempts by each team</li>'
                    '<li><strong>Results</strong> &mdash; Best run per team per category</li></ul>'
                    + IMG_PH +
                    '<h3>Roles</h3>'
                    '<ul><li><strong>Organiser</strong> &mdash; Creates the contest, configures categories, registers teams</li>'
                    '<li><strong>Judge</strong> &mdash; Operates runs, enters scores for judged categories</li>'
                    '<li><strong>Team</strong> &mdash; Students who compete with their robot</li></ul>'
                ),
            },
            {
                'slug': 'judge-guide',
                'title': 'Judge Guide',
                'nav_section': 'organize',
                'nav_order': 3,
                'body': (
                    '<h2>Judge Guide</h2>'
                    '<p>How to operate a RoboSTEAM competition round using the Competition Platform.</p>'
                    '<h3>Before the competition</h3>'
                    '<ol><li>Log in at <a href="/accounts/login/">Judge Login</a>.</li>'
                    '<li>Navigate to the Contest and select the Category you are judging.</li>'
                    '<li>Verify the lap timer device is Online (for timed categories).</li>'
                    '<li>Set the competition state to RUNNING.</li></ol>'
                    '<h3>Running a timed round</h3>'
                    '<ol><li>Select the next team and click <strong>Create Run</strong>.</li>'
                    '<li>Click <strong>Start</strong>. The server sends START to the lap timer and robot.</li>'
                    '<li>The lap timer records crossings automatically. Run completes when laps are done.</li>'
                    '<li>Click <strong>Void</strong> if the run must be cancelled.</li></ol>'
                    + IMG_PH +
                    '<h3>Running a judged round</h3>'
                    '<ol><li>Create a run for the team.</li>'
                    '<li>Click Start to begin.</li>'
                    '<li>Enter a score (1&ndash;100) and optional comment. Click <strong>Score</strong>.</li></ol>'
                    '<h3>Manual entry (MQTT fallback)</h3>'
                    '<p>If the MQTT connection is lost, the run is automatically voided. Use the Manual Entry form to enter the time or score recorded manually.</p>'
                ),
            },
            {
                'slug': 'video-scoreboard',
                'title': 'Video – Scoreboard Application',
                'nav_section': 'organize',
                'nav_order': 4,
                'body': (
                    '<h2>Video: Scoreboard Application</h2>'
                    '<p>Watch this tutorial to learn how to use the RoboSTEAM Competition Scoreboard.</p>'
                    + VID_PH +
                    '<p><em>Instructional video coming soon. Contact your local organiser for a live demonstration.</em></p>'
                ),
            },
        ]

        for page_data in pages:
            StaticPage.objects.get_or_create(
                slug=page_data['slug'],
                defaults={
                    'title': page_data['title'],
                    'nav_section': page_data['nav_section'],
                    'nav_order': page_data['nav_order'],
                    'body': page_data['body'],
                    'is_published': True,
                }
            )

    def _seed_news(self, admin_user):
        from public.models import NewsPost
        posts = [
            {
                'title': 'What is a Competition and How Does it Look?',
                'body': (
                    '<h2>What is a Competition and How Does it Look?</h2>'
                    '<p>Robot competitions are educational events where student teams test their robots against structured challenges. Here is what to expect at a RoboSTEAM competition event.</p>'
                    + IMG_PH +
                    '<h3>The experience</h3>'
                    '<p>Teams arrive, check in their robots for technical inspection, then get practice time on the competition tracks. The action happens during qualifying rounds.</p>'
                    '<p>The live scoreboard updates in real time as each run is completed.</p>'
                    + IMG_PH +
                    '<h3>What makes it educational?</h3>'
                    '<p>Students gain experience in engineering design, debugging under pressure, teamwork, and presenting their work.</p>'
                ),
                'published_at': datetime.datetime(2023, 1, 4, 12, 0, tzinfo=datetime.timezone.utc),
            },
            {
                'title': 'RoboSTEAM Competitions Platform Launched',
                'body': (
                    '<h2>RoboSTEAM Competitions Platform Launched</h2>'
                    '<p>We are pleased to announce the launch of the RoboSTEAM Competition Platform, part of the ROBO STEAM ACADEMY Erasmus+ project.</p>'
                    '<h3>Key features</h3>'
                    '<ul><li>Automated lap timing via hardware IR sensor integration</li>'
                    '<li>Real-time scoreboard with WebSocket push updates</li>'
                    '<li>Support for both timed and judged competition categories</li>'
                    '<li>Open-source PicoBot library for student robots (Raspberry Pi Pico W)</li>'
                    '<li>MQTT-based robot control and lap timer communication</li></ul>'
                    + IMG_PH +
                    '<p>The platform is developed as part of WP3 (Advanced Robo STEM Games and Jury) and will be deployed at partner schools in Bulgaria, Slovakia, and Romania.</p>'
                ),
                'published_at': datetime.datetime(2026, 6, 28, 10, 0, tzinfo=datetime.timezone.utc),
            },
            {
                'title': 'Video: How to Use the Competition Scoreboard',
                'body': (
                    '<h2>Video: How to Use the Competition Scoreboard</h2>'
                    '<p>This tutorial walks judges and organisers through the RoboSTEAM Competition Scoreboard application.</p>'
                    + VID_PH +
                    '<p>Topics covered: logging in, creating runs, starting timed runs, entering scores, and reading the live scoreboard.</p>'
                    '<p><em>Full instructional video coming soon.</em></p>'
                ),
                'published_at': datetime.datetime(2026, 6, 1, 10, 0, tzinfo=datetime.timezone.utc),
            },
        ]

        for post_data in posts:
            NewsPost.objects.get_or_create(
                title=post_data['title'],
                defaults={
                    'body': post_data['body'],
                    'published_at': post_data['published_at'],
                    'is_published': True,
                    'author': admin_user,
                }
            )

    def _seed_announcements(self):
        from public.models import Announcement
        Announcement.objects.get_or_create(
            title='RoboSTEAM 2027 Spring Competition',
            defaults={
                'event_date': datetime.date(2027, 3, 15),
                'location': 'Sofia, Bulgaria (TBC)',
                'short_description': 'The next RoboSTEAM international competition. Registration opens January 2027.',
                'registration_link': '',
                'is_published': True,
            }
        )

    def _seed_gallery(self):
        from public.models import GalleryAlbum
        GalleryAlbum.objects.get_or_create(
            title='Sample Gallery — Photos Coming Soon',
            defaults={
                'event_date': datetime.date(2026, 1, 1),
                'description': 'Photos from RoboSTEAM competitions will appear here.',
                'is_published': False,
            }
        )
