-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- Host: localhost    Database: hackathon
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `ce - facculty`
--

DROP TABLE IF EXISTS `ce - facculty`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ce - facculty` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(45) NOT NULL,
  `email` varchar(45) NOT NULL,
  `Max Units` int NOT NULL,
  `Current Units` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idce - facculty_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ce - facculty`
--

LOCK TABLES `ce - facculty` WRITE;
/*!40000 ALTER TABLE `ce - facculty` DISABLE KEYS */;
INSERT INTO `ce - facculty` VALUES (1,'Jennie Roque','jennieroque@gmail.com',40,30),(2,'Robert Chen','robert.chen@example.edu',40,27),(3,'Marcus Vance','s.jenkins@fictionalcollege.edu',40,16),(4,'Elena Rodriguez','mvance@dummy-university.edu',40,25),(5,'Arthur Pendelton','elena.rodriguez@academia-test.edu',40,12),(6,'Linda Al-Fayed','a.pendelton@example-state.edu',40,32),(7,'Robert Chen','l.alfayed@tech-example.edu',40,26),(8,'James Connor','j.connor@university-placeholder.edu',40,13);
/*!40000 ALTER TABLE `ce - facculty` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ce - sections`
--

DROP TABLE IF EXISTS `ce - sections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ce - sections` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `Section` varchar(45) NOT NULL,
  `Year Level` int NOT NULL,
  `Student Count` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idce - sections_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ce - sections`
--

LOCK TABLES `ce - sections` WRITE;
/*!40000 ALTER TABLE `ce - sections` DISABLE KEYS */;
INSERT INTO `ce - sections` VALUES (1,'CE - 1A',1,42),(2,'CE - 1B',1,42),(3,'CE - 1C',1,42),(4,'CE - 2A',2,42),(5,'CE - 2B',2,42),(6,'CE - 3A',3,42),(7,'CE - 3B',3,42),(8,'CE - 4A',4,42),(9,'CE - 4B',4,42);
/*!40000 ALTER TABLE `ce - sections` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ce - subjects`
--

DROP TABLE IF EXISTS `ce - subjects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ce - subjects` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `Code` varchar(45) NOT NULL,
  `Course Name` varchar(150) NOT NULL,
  `No. of Units` int NOT NULL,
  `Subject Type` varchar(45) NOT NULL,
  `Total Hours` int NOT NULL,
  `Year Level` int NOT NULL,
  `Semester` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=89 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ce - subjects`
--

LOCK TABLES `ce - subjects` WRITE;
/*!40000 ALTER TABLE `ce - subjects` DISABLE KEYS */;
INSERT INTO `ce - subjects` VALUES (1,'MMW 101','Mathematics in the Modern World',3,'Lecture',3,1,1),(2,'UTS 101','Understanding the Self',3,'Lecture',3,1,1),(3,'PAL 101','Panitikan at Lipunan',3,'Lecture',3,1,1),(4,'PCM 101','Purposive Communication',3,'Lecture',3,1,1),(5,'ETH 101','Ethics',3,'Lecture',3,1,1),(6,'COE 100','Mathematics for Engineers',3,'Lecture',3,1,1),(7,'COE 101','Introduction to Engineering',1,'Lecture',1,1,1),(8,'COE 102','Calculus 1',3,'Lecture',3,1,1),(9,'COE 103','Chemistry for Engineers',3,'Lecture',3,1,1),(10,'COE 103L','Chemistry for Engineers Laboratory',1,'Lab',3,1,1),(11,'PE 10','PATHFIT 1',2,'Lecture',2,1,1),(12,'NSTP 10','National Service Training Program 1',3,'Lecture',3,1,1),(13,'RPH 101','Readings in Philippine History',3,'Lecture',3,1,2),(14,'TCW 101','The Contemporary World',3,'Lecture',3,1,2),(15,'AAP 101','Art Appreciation',3,'Lecture',3,1,2),(16,'COE 104','Calculus 2 (Integral Calculus)',3,'Lecture',3,1,2),(17,'COE 105','Physics for Engineers - Lecture (Calculus Based)',3,'Lecture',3,1,2),(18,'COE 105L','Physics for Engineers - Laboratory (Calculus Based)',1,'Lab',3,1,2),(19,'CIV 101','Mathematics for Civil Engineers',3,'Lecture',3,1,2),(20,'CIV 102','Civil Engineering Orientation',2,'Lecture',2,1,2),(21,'CIV 103D','Engineering Drawing and Plans',1,'Lab',3,1,2),(22,'CIV 104','Computer Fundamentals and Programming',2,'Lab',6,1,2),(23,'PE 11','PATHFIT 2',2,'Lecture',2,1,2),(24,'NSTP 11','NSTP 2',3,'Lecture',3,1,2),(25,'COE 201','Differential Equations',3,'Lecture',3,2,1),(26,'COE 202','Engineering Data Analysis',3,'Lecture',3,2,1),(27,'CIV 201','Statics of Rigid Bodies',3,'Lecture',3,2,1),(28,'CIV 202','Fundamentals of Surveying 1 (Lecture)',3,'Lecture',3,2,1),(29,'CIV 202F','Fundamentals of Surveying 1 (Field)',1,'Lab',3,2,1),(30,'CIV 203','Geology for Civil Engineers',2,'Lecture',2,2,1),(31,'CIV 204','Building Systems Design (Lecture)',2,'Lecture',2,2,1),(32,'CIV 204D','Building Systems Design (Design)',1,'Lab',3,2,1),(33,'CIV 205L','Computer-Aided Drafting (Laboratory)',1,'Lab',3,2,1),(34,'SSP 101d','The Entrepreneurial Mind',3,'Lecture',3,2,1),(35,'PE 12','PATHFit 3',2,'Lecture',2,2,1),(36,'CIV 206','Dynamics of Rigid Bodies',2,'Lecture',2,2,2),(37,'CIV 207','Mechanics of Deformable Bodies',4,'Lecture',4,2,2),(38,'CIV 208','Numerical Solutions to CE Problems (Lecture)',2,'Lecture',2,2,2),(39,'CIV 208L','Numerical Solutions to CE Problems (Laboratory)',1,'Lab',3,2,2),(40,'CIV 209F','Fundamentals of Surveying 2 (Field)',1,'Lab',3,2,2),(41,'CIV 210','Engineering Economics',3,'Lecture',3,2,2),(42,'CIV 211','Engineering Utilities 1',3,'Lecture',3,2,2),(43,'CIV 212','Engineering Utilities 2',3,'Lecture',3,2,2),(44,'AE 101','Academic English',3,'Lecture',3,2,2),(45,'STS 101','Science, Technology and Society',3,'Lecture',3,2,2),(46,'PE 13','PATHFit 4',2,'Lecture',2,2,2),(47,'CIV 301','Structural Theory 1 (Lecture)',2,'Lecture',2,3,1),(48,'CIV 301D','Structural Theory 1 (Design)',1,'Lab',3,3,1),(49,'CIV 302','Soil Mechanics (Lecture)',3,'Lecture',3,3,1),(50,'CIV 302L','Soil Mechanics (Laboratory)',1,'Lab',3,3,1),(51,'CIV 303','Hydraulics 1',3,'Lecture',3,3,1),(52,'CIV 304','Construction Material and Testing (Lecture)',2,'Lecture',2,3,1),(53,'CIV 304L','Construction Material and Testing (Laboratory)',1,'Lab',3,3,1),(54,'CIV 305','Highway and Railroad Engineering',3,'Lecture',3,3,1),(55,'CIV 306','Engineering Management',2,'Lecture',2,3,1),(56,'CIV 307','Environmental Engineering',2,'Lecture',2,3,1),(57,'CIV 308','Quantity Surveying (Lecture)',1,'Lecture',1,3,1),(58,'CIV 308L','Quantity Surveying (Laboratory)',1,'Lab',3,3,1),(59,'CIV 309','Structural Theory 2 (Lecture)',2,'Lecture',2,3,2),(60,'CIV 309D','Structural Theory 2 (Design)',1,'Lab',3,3,2),(61,'CIV 310','Hydraulics 2 (Lecture)',2,'Lecture',2,3,2),(62,'CIV 310L','Hydraulics 2 (Laboratory)',1,'Lab',3,3,2),(63,'CIV 311','Construction Methods and Project Management',3,'Lecture',3,3,2),(64,'CIV 312','Foundation Engineering (Lecture)',2,'Lecture',2,3,2),(65,'CIV 312L','Foundation Engineering (Laboratory)',1,'Lab',3,3,2),(66,'CIV 313','Technopreneurship 101',3,'Lecture',3,3,2),(67,'CIV 314','Principles of Transportation Engineering',3,'Lecture',3,3,2),(68,'CIV 315','Hydrology',3,'Lecture',3,3,2),(69,'CIV 316','Earthquake Engineering (Design)',1,'Lab',3,3,2),(70,'CIV 401','Structural Steel and Timber Design (Lecture)',3,'Lecture',3,4,1),(71,'CIV 401D','Structural Steel and Timber Design (Design)',1,'Lab',3,4,1),(72,'CIV 402','Reinforced Concrete Design (Lecture)',3,'Lecture',3,4,1),(73,'CIV 402D','Reinforced Concrete Design (Design)',1,'Lab',3,4,1),(74,'CIV 403','Civil Engineering Project Part 1 (Lecture)',1,'Lecture',1,4,1),(75,'CIV 403D','Civil Engineering Project Part 1 (Design)',1,'Lab',3,4,1),(76,'CIV 404','Water Resources Engineering',2,'Lecture',2,4,1),(77,'CIV 405','Correlation 1',1,'Lab',3,4,1),(78,'CIV 410-CEM','Construction Occupational Safety and Health (SPECIALIZATION)',3,'Lecture',3,4,1),(79,'CIV 411-CEM','Project Construction and Management (SPECIALIZATION)',3,'Lecture',3,4,1),(80,'CIV 406','Civil Engineering Project Part 2 (Lecture)',1,'Lecture',1,4,2),(81,'CIV 406D','Civil Engineering Project Part 2 (Design)',1,'Lab',3,4,2),(82,'CIV 407F','Seminars and Plant Visits',1,'Lab',3,4,2),(83,'CIV 408','CE Laws, Ethics and Contracts',2,'Lecture',2,4,2),(84,'CIV 409','Correlation 2',1,'Lab',3,4,2),(85,'CIV 412-CEM','Construction Cost Engineering (SPECIALIZATION)',3,'Lecture',3,4,2),(86,'CIV 413-CEM','Special Topics (SPECIALIZATION)',3,'Lecture',3,4,2),(87,'CIV 414-CEM','Computer Software in Construction Management (SPECIALIZATION)',3,'Lecture',3,4,2),(88,'RLW 101','Life and Works of Rizal',3,'Lecture',3,4,2);
/*!40000 ALTER TABLE `ce - subjects` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ece - facculty`
--

DROP TABLE IF EXISTS `ece - facculty`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ece - facculty` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(45) NOT NULL,
  `email` varchar(45) NOT NULL,
  `Max Units` int NOT NULL,
  `Current Units` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ece - facculty`
--

LOCK TABLES `ece - facculty` WRITE;
/*!40000 ALTER TABLE `ece - facculty` DISABLE KEYS */;
INSERT INTO `ece - facculty` VALUES (1,'William Hastings','w.hastings@fictional.edu',40,27),(2,'Maria Gonzalez','mgonzalez@example-university.edu',40,16),(3,'David Kim','david.kim@dummy-college.edu',40,25),(4,'Elizabeth Barnes','e.barnes@academia-test.edu',40,12),(5,'Richard Thompson','rthompson@example-state.edu',40,32),(6,'Wei Lin','wei.lin@tech-example.edu',40,26),(7,'Thomas Wright','smitchell@university-placeholder.edu',40,26),(8,'Susan Mitchell','t.wright@mock-edu.org',40,13);
/*!40000 ALTER TABLE `ece - facculty` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ece - sections`
--

DROP TABLE IF EXISTS `ece - sections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ece - sections` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `Section` varchar(45) NOT NULL,
  `Year Level` int NOT NULL,
  `Student Count` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idece - sections_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ece - sections`
--

LOCK TABLES `ece - sections` WRITE;
/*!40000 ALTER TABLE `ece - sections` DISABLE KEYS */;
INSERT INTO `ece - sections` VALUES (1,'ECE - 1A',1,42),(2,'ECE - 1B',1,42),(3,'ECE - 1C',1,42),(4,'ECE - 2A',2,42),(5,'ECE - 2B',2,42),(6,'ECE - 3A',3,42),(7,'ECE - 3B',3,42),(8,'ECE - 4A',4,42),(9,'ECE - 4B',4,42);
/*!40000 ALTER TABLE `ece - sections` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ece - subjects`
--

DROP TABLE IF EXISTS `ece - subjects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ece - subjects` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `Code` varchar(45) NOT NULL,
  `Course Name` varchar(150) NOT NULL,
  `No. of Units` int NOT NULL,
  `Subject Type` varchar(45) NOT NULL,
  `Total Hours` int NOT NULL,
  `Year Level` int NOT NULL,
  `Semester` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=88 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ece - subjects`
--

LOCK TABLES `ece - subjects` WRITE;
/*!40000 ALTER TABLE `ece - subjects` DISABLE KEYS */;
INSERT INTO `ece - subjects` VALUES (1,'MMW 101','Mathematics in the Modern World',3,'Lecture',3,1,1),(2,'UTS 101','Understanding the Self',3,'Lecture',3,1,1),(3,'PAL 101','Panitikan at Lipunan',3,'Lecture',3,1,1),(4,'PCM 101','Purposive Communication',3,'Lecture',3,1,1),(5,'ETH 101','Ethics',3,'Lecture',3,1,1),(6,'COE 100','Mathematics for Engineers',3,'Lecture',3,1,1),(7,'COE 101','Introduction to Engineering',1,'Lecture',1,1,1),(8,'COE 102','Calculus 1',3,'Lecture',3,1,1),(9,'COE 103','Chemistry for Engineers',3,'Lecture',3,1,1),(10,'COE 103L','Chemistry for Engineers Laboratory',1,'Lab',3,1,1),(11,'PE 10','PATHFIT 1',2,'Lecture',2,1,1),(12,'NSTP 10','NSTP',3,'Lecture',3,1,1),(13,'AE 101','Academic English',3,'Lecture',3,1,2),(14,'STS 101','Science, Technology, and Society',3,'Lecture',3,1,2),(15,'TCW 101','The Contemporary World',3,'Lecture',3,1,2),(16,'COE 104','Calculus 2',3,'Lecture',3,1,2),(17,'COE 105','Physics for Engineers Lecture',3,'Lecture',3,1,2),(18,'COE 105L','Physics for Engineers Laboratory',1,'Lab',3,1,2),(20,'ECE 101L','Computer-Aided Design',1,'Lab',3,1,2),(21,'ECE 102','Materials Science and Engineering',3,'Lecture',3,1,2),(22,'ECE 103','Physics 2',3,'Lecture',3,1,2),(23,'ECE 103L','Physics 2 (Lab)',1,'Lab',3,1,2),(24,'PE 11','PATHFIT 2',2,'Lecture',2,1,2),(25,'NSTP 11','NSTP 2',3,'Lecture',3,1,2),(26,'RPH 101','Readings in Philippine History',3,'Lecture',3,2,1),(27,'COE 201','Differential Equation',3,'Lecture',3,2,1),(28,'ECE 201','Engineering Economics',3,'Lecture',3,2,1),(29,'ECE 202','Circuits 1',3,'Lecture',3,2,1),(30,'ECE 202L','Circuits 1 (Laboratory)',1,'Lab',3,2,1),(31,'ECE 203','Electronics 1: Electronics Devices and Circuits',3,'Lecture',3,2,1),(32,'ECE 203L','Electronics 1L: Electronics Devices and Circuits (Laboratory)',1,'Lab',3,2,1),(33,'ECE 204','ECE Laws, Contracts, Ethics, Standards, and Safety',3,'Lecture',3,2,1),(34,'ECE 205','Electronics Shops and Practices',1,'Lab',3,2,1),(35,'ECE 206','Computer Programming (Object Oriented Programming)',2,'Lab',6,2,1),(36,'PE 12','PATHFIT 3',2,'Lecture',2,2,1),(37,'AAP 101','Art Appreciation',3,'Lecture',3,2,2),(38,'ECE 207','Advanced Engineering Mathematics for ECE',3,'Lecture',3,2,2),(39,'ECE 207L','Advanced Engineering Mathematics for ECE (Laboratory)',1,'Lab',3,2,2),(40,'ECE 208','Circuits 2',3,'Lecture',3,2,2),(41,'ECE 208L','Circuits 2 (Laboratory)',1,'Lab',3,2,2),(42,'ECE 209','Electronics 2: Electronic Circuit Analysis and Desgin',3,'Lecture',3,2,2),(43,'ECE 209L','Electronics 2: Electronic Circuit Analysis and Desgin (Laboratory)',1,'Lab',3,2,2),(44,'ECE 210','Communications 1: Principles of Communication Systems',3,'Lecture',3,2,2),(45,'ECE 210L','Communications 1: Principles of Communication Systems (Laboratory)',1,'Lab',3,2,2),(46,'ECE 211','Electromagnets',4,'Lecture',4,2,2),(47,'PE 13','PATHFIT 4',2,'Lecture',2,2,2),(48,'SSP 101d','Entrepreneurial Mind',3,'Lecture',3,3,1),(49,'ECE 301','Digital Electronics 1: Logic Circuits and Switching Theory',3,'Lecture',3,3,1),(50,'ECE 301L','Digital Electronics 1: Logic Circuits and Switching Theory (Laboratory)',1,'Lab',3,3,1),(51,'ECE 302','Electronics 3: Electronic System and Design',3,'Lecture',3,3,1),(52,'ECE 302L','Electronics 3: Electronic System and Design (Laboratory)',1,'Lab',3,3,1),(53,'ECE 303','Signals, Spectra, and Signal Processing',3,'Lecture',3,3,1),(54,'ECE 303L','Signals, Spectra, and Signal Processing (Laboratory)',1,'Lab',3,3,1),(55,'ECE 304','Communications 2: Modulation and Coding Techniques',3,'Lecture',3,3,1),(56,'ECE 304L','Communications 2: Modulation and Coding Techniques (Laboratory)',1,'Lab',3,3,1),(57,'ECE 305','Engineering Data Analysis',3,'Lecture',3,3,1),(58,'ECE 306','Enegineering Management',3,'Lecture',3,3,1),(59,'ECE 307','Environmental Science and Engineering',3,'Lecture',3,3,2),(60,'ECE 308','Communications 3: Data Communications',3,'Lecture',3,3,2),(61,'ECE 308L','Communications 3L: Data Communications (Laboratory)',1,'Lab',3,3,2),(62,'ECE 309','Communications 4: Transmission Media, Antenna System, and Design',3,'Lecture',3,3,2),(63,'ECE 309L','Communications 4L: Transmission Media, Antenna System, and Design (Laboratory)',1,'Lab',3,3,2),(64,'ECE 310','Digital Electronics 2: Microprocessor & Microcontroller Systems and Design',3,'Lecture',3,3,2),(65,'ECE 310L','Digital Electronics 2L: Microprocessor & Microcontroller Systems and Design (Laboratory)',1,'Lab',3,3,2),(66,'ECE 311','Feedback and Control Systems',3,'Lecture',3,3,2),(67,'ECE 311L','Feedback and Control Systems (Laboratory)',1,'Lab',3,3,2),(68,'ECE 312','Methods of Research',3,'Lecture',3,3,2),(69,'ECE401','Technopreneurship',3,'Lecture',3,4,1),(70,'ECE402','Design 1 / Capstone Project 1',1,'Lab',3,4,1),(71,'ECE403','Advanced Communication System & Design',3,'Lecture',3,4,1),(72,'ECE403L','Advanced Communication System & Design (Laboratory)',1,'Lab',3,4,1),(73,'ECE404','Advanced Programming for ECE',3,'Lecture',3,4,1),(74,'ECE404L','Advanced Programming for ECE (Laboratory)',1,'Lab',3,4,1),(75,'ECE405','ICT Infrastructure',3,'Lecture',3,4,1),(76,'ECE405L','ICT Infrastructure (Laboratory)',1,'Lab',3,4,1),(77,'ECE406','ECE Correlation 1: Mathematics',1,'Lab',3,4,1),(78,'ECE407','ECE Correlation 2: Electronics',1,'Lab',3,4,1),(79,'RLW 101','Rizal Life and Works',3,'Lecture',3,4,2),(80,'ECE 408','ECE Plant Visits / Seminars / Colloquium',1,'Lab',3,4,2),(81,'ECE 409','Design 2 / Capstone Project 2',1,'Lab',3,4,2),(82,'ECE 410','ECE Correlation 3: GEAS',1,'Lab',3,4,2),(83,'ECE 411','ECE Correlation 4: EST',1,'Lab',3,4,2),(84,'ECE 412','Electronics Ancillary System',3,'Lecture',3,4,2),(85,'ECE 412L','Electronics Ancillary System (Laboratory)',1,'Lab',3,4,2),(86,'ECE 413','Advanced Networking',3,'Lecture',3,4,2),(87,'ECE 413L','Advanced Networking (Laboratory)',1,'Lab',3,4,2);
/*!40000 ALTER TABLE `ece - subjects` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `mee - facculty`
--

DROP TABLE IF EXISTS `mee - facculty`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mee - facculty` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(45) NOT NULL,
  `email` varchar(45) NOT NULL,
  `Max Units` int NOT NULL,
  `Current Units` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `mee - facculty`
--

LOCK TABLES `mee - facculty` WRITE;
/*!40000 ALTER TABLE `mee - facculty` DISABLE KEYS */;
INSERT INTO `mee - facculty` VALUES (1,'Jewel T. Serrano','jserrano@emeel.com',40,30),(2,'Jason D. Lozano','jlozano@emeel.com',40,30),(3,'Margarette S. Jumaquio','mjumaquio@emeel.com',40,30),(4,'Gabriel Angelo V. Pascual','gpascual@emeel.com',40,30),(5,'Kristine Bugayong','kbugayong@emeel.com',40,30),(6,'Juan Martin R. Cruz','jcruz@emeel.com',40,30),(7,'Jerome B. Bagsic','jbagsic@emeel.com',40,30),(8,'Arvin Julius S. Tullao','atullao@emeel.com',40,30),(9,'Nasher G. Jimenez','njimenez@emeel.com',40,30);
/*!40000 ALTER TABLE `mee - facculty` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `mee - sections`
--

DROP TABLE IF EXISTS `mee - sections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mee - sections` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `Section` varchar(45) NOT NULL,
  `Year Level` int NOT NULL,
  `Student Count` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `mee - sections`
--

LOCK TABLES `mee - sections` WRITE;
/*!40000 ALTER TABLE `mee - sections` DISABLE KEYS */;
INSERT INTO `mee - sections` VALUES (10,'MEE-1A',1,42),(11,'MEE-1B',1,42),(12,'MEE-1C',1,42),(13,'MEE-2A',2,42),(14,'MEE-2B',2,42),(15,'MEE-3A',3,42),(16,'MEE-3B',3,42),(17,'MEE-4A',4,42),(18,'MEE-4B',4,42);
/*!40000 ALTER TABLE `mee - sections` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `mee - subjects`
--

DROP TABLE IF EXISTS `mee - subjects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mee - subjects` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `Code` varchar(45) NOT NULL,
  `Course Name` varchar(150) NOT NULL,
  `No. of Units` int NOT NULL,
  `Subject Type` varchar(150) NOT NULL,
  `Total Hours` int NOT NULL,
  `Year Level` int NOT NULL,
  `Semester` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=97 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `mee - subjects`
--

LOCK TABLES `mee - subjects` WRITE;
/*!40000 ALTER TABLE `mee - subjects` DISABLE KEYS */;
INSERT INTO `mee - subjects` VALUES (1,'MMW 101','Mathematics in the Modern World',3,'Lecture',3,1,1),(2,'UTS 101','Understanding the Self',3,'Lecture',3,1,1),(3,'PAL 101','Panitikan at Lipunan',3,'Lecture',3,1,1),(4,'PCM 101','Purposive Communication',3,'Lecture',3,1,1),(5,'ETH 101','Ethics',3,'Lecture',3,1,1),(6,'COE 100','Mathematics for Engineers',3,'Lecture',3,1,1),(7,'COE 101','Introduction to Engineering',1,'Lecture',1,1,1),(8,'COE 102','Calculus 1',3,'Lecture',3,1,1),(9,'COE 103','Chemistry for Engineers',3,'Lecture',3,1,1),(10,'COE 103L','Chemistry for Engineers Laboratory',1,'Lab',3,1,1),(11,'PE 10','PATHFIT 1',2,'Lecture',2,1,1),(12,'NSTP 10','NSTP',3,'Lecture',3,1,1),(13,'COE 104','Calculus 2',3,'Lecture',3,1,2),(14,'COE 105','Physics for Engineers Lecture',3,'Lecture',3,1,2),(15,'COE 105L','Physics for Engineers Laboratory',1,'Lab',3,1,2),(16,'AE 101','Academic English',3,'Lecture',3,1,2),(17,'STS','Science, Technology, and Society',3,'Lecture',3,1,2),(18,'MEE 101','Introduction to Mechatronics Engineering',1,'Lecture',1,1,2),(19,'MEE 103','Engineering Drawing',1,'Lab',3,1,2),(20,'MEE 104L','Computer Programming',1,'Lab',3,1,2),(21,'RPH 101','Readings in Philippine History',3,'Lecture',3,1,2),(22,'PE 11','PATHFIT 2',2,'Lecture',2,1,2),(23,'NSTP 11','NSTP 2',3,'Lecture',3,1,2),(24,'TCW 101','The Contemporary World',3,'Lecture',3,1,2),(25,'COE 201','Differential Equation',3,'Lecture',3,2,1),(26,'COE 202','Engineering Data Analysis',3,'Lecture',3,2,1),(27,'AAP 101','Art Appreciation',3,'Lecture',3,2,1),(28,'MEE 201','Electric Circuits Analysis I',3,'Lecture',3,2,1),(29,'MEE 201L','Electric Circuits Analysis I Laboratory',1,'Lab',3,2,1),(30,'MEE 202','Electronics',3,'Lecture',3,2,1),(31,'MEE 202L','Electronics Laboratory',1,'Lab',3,2,1),(32,'MEE 203','Thermodynamics',3,'Lecture',3,2,1),(33,'MEE 204','Engineering Mechanics',3,'Lecture',3,2,1),(34,'PE 12','PATHFIT 3',2,'Lecture',2,2,1),(35,'MEE 211L','Computer Aided Drafting and Design (2D)',1,'Lab',3,2,1),(36,'MEE 205','Advanced Engineering Mathematics',3,'Lecture',3,2,2),(37,'MEE 206','Mechanical Processes',1,'Lecture',1,2,2),(38,'MEE 206L','Mechanical Processes Laboratory',1,'Lab',3,2,2),(39,'MEE 207','Electric Circuits Analysis II',3,'Lecture',3,2,2),(40,'MEE 207L','Electric Circuits Analysis II Laboratory',1,'Lab',3,2,2),(41,'MEE 208','Industrial Electronics',3,'Lecture',3,2,2),(42,'MEE 208L','Industrial Electronics Laboratory',1,'Lab',3,2,2),(43,'MEE 209','Fluid Technology I',2,'Lecture',2,2,2),(44,'MEE 209L','Fluid Technology I Laboratory',1,'Lab',3,2,2),(45,'MEE 210','Mechanics of Deformable Bodies',3,'Lecture',3,2,2),(46,'PE 13','PATHFIT 4',2,'Lecture',2,2,2),(47,'MEE 212L','Computer Aided Drafting and Design (3D)',1,'Lab',3,2,2),(48,'SSP 101d','Entrepreneurial Mind',3,'Lecture',3,3,1),(49,'MEE 301','Safety of Mechatronics Systems',2,'Lecture',2,3,1),(50,'MEE 302','Electromechanical Energy Conversion',3,'Lecture',3,3,1),(51,'MEE 302L','Electromechanical Energy Conversion Laboratory',1,'Lab',3,3,1),(52,'MEE 303D','Machine Design',1,'Lab',3,3,1),(53,'MEE 304','Logic Circuit and Switching Theory',2,'Lecture',2,3,1),(54,'MEE 304L','Logic Circuit and Switching Theory\nLaboratory',1,'Lab',3,3,1),(55,'MEE 305','Computer Numerical Control',2,'Lecture',2,3,1),(56,'MEE 305L','Computer Numerical Control Laboratory',1,'Lab',3,3,1),(57,'MEE 306','Fluid Technology II',2,'Lecture',2,3,1),(58,'MEE 306L','Fluid Technology II Laboratory',1,'Lab',3,3,1),(59,'MEE 313L','Database Management System',1,'Lab',3,3,1),(60,'MEE 307','Mechatronics Standards and Ethics',2,'Lecture',2,3,1),(61,'MEE 308','Methods of Research',3,'Lecture',3,3,2),(62,'MEE 309','Control Systems',2,'Lecture',2,3,2),(63,'MEE 309L','Control Systems Laboratory',1,'Lab',3,3,2),(64,'MEE 310D','Electric Drives and Control Design',1,'Lab',3,3,2),(65,'MEE 310L','Electric Drives and Control Laboratory',1,'Lab',3,3,2),(66,'MEE 311L','Programmable Logic Controller',2,'Lab',6,3,2),(67,'MEE 312','MicroController and MicroProcessor',2,'Lecture',2,3,2),(68,'MEE 312L','MicroController and MicroProcessor Laboratory',1,'Lab',3,3,2),(69,'MEE 315','Engineering Economy and Accounting',3,'Lecture',3,3,2),(70,'MEE 316','Technopreneurship',3,'Lecture',3,3,2),(71,'RLW 101','Rizal Life and Works',3,'Lecture',3,3,2),(72,'MEE 401','Engineering Management',2,'Lecture',2,4,1),(73,'MEE 402D','Project Study',1,'Lab',3,4,1),(74,'MEE 403D','Artificial Intelligence',1,'Lab',3,4,1),(75,'MEE 404','Computer Numerical Control 2',2,'Lecture',2,4,1),(76,'MEE 404L','Computer Numerical Control 2 Laboratory',1,'Lab',3,4,1),(77,'MEE 405L','Advanced Computer Programming',1,'Lab',3,4,1),(78,'MEE 406','Process Instrumentation and Control',3,'Lecture',3,4,1),(79,'MEE 406L','Process Instrumentation and Control Laboratory',1,'Lab',3,4,1),(80,'MEE 407','Motion Control Technology',2,'Lecture',2,4,1),(81,'MEE 407L','Motion Control Technology Laboratory',1,'Lab',3,4,1),(82,'MEE 408L','Industrial Data Communication and Network System',1,'Lab',3,4,1),(83,'MEE 409','Elective 1',3,'Lecture',3,4,1),(84,'MEE 417','Environmental Engineering',3,'Lecture',3,4,1),(85,'MEE 410D','Project Study II',1,'Lab',3,4,2),(86,'MEE 411D','Industrial Robotics and Design',1,'Lab',3,4,2),(87,'MEE 411L','Industrial Robotics Laboratory',1,'Lab',3,4,2),(88,'MEE 412D','Machine Vision System and Design',1,'Lab',3,4,2),(89,'MEE 412L','Machine Vision System Laboratory',1,'Lab',3,4,2),(90,'MEE 413D','SCADA and HMI Design',1,'Lab',3,4,2),(91,'MEE 413L','SCADA and HMI\nLaboratory',1,'Lab',3,4,2),(92,'MEE 414','Mechatronics Systems Integration and Troubleshooting',1,'Lecture',1,4,2),(93,'MEE 414L','Mechatronics Systems Integration and Troubleshooting Laboratory',1,'Lab',3,4,2),(94,'MEE 415F','Seminars and Fieldtrips',2,'Lab',6,4,2),(95,'MEE 416','Elective 2',3,'Lecture',3,4,2),(96,'MEE 418','Comprehensive Examination',1,'Lab',3,4,2);
/*!40000 ALTER TABLE `mee - subjects` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `mfe - facculty`
--

DROP TABLE IF EXISTS `mfe - facculty`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mfe - facculty` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(45) NOT NULL,
  `email` varchar(45) NOT NULL,
  `Max Units` int NOT NULL,
  `Current Units` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idmfe- facculty_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `mfe - facculty`
--

LOCK TABLES `mfe - facculty` WRITE;
/*!40000 ALTER TABLE `mfe - facculty` DISABLE KEYS */;
INSERT INTO `mfe - facculty` VALUES (1,'Michael Chang','m.chang@example-institute.edu',40,30),(2,'Catherine Patel','cpatel@fictional-u.edu',40,30),(3,'Jessica Nguyen','j.nguyen@tech-example.edu',40,30),(4,'Samuel Clark','sclark@university-placeholder.edu',40,30),(5,'Rachel Foster','rfoster@academia-test.edu',40,30),(6,'Christopher Lewis','clewis@example.edu',40,30),(7,'Amanda Torres','amanda.torres@mock-college.edu',40,30),(8,'Jonathan Reed','jreed@dummy-state.edu',40,30);
/*!40000 ALTER TABLE `mfe - facculty` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `mfe - sections`
--

DROP TABLE IF EXISTS `mfe - sections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mfe - sections` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `Section` varchar(45) NOT NULL,
  `Year Level` int NOT NULL,
  `Student Count` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idmfe - sections_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `mfe - sections`
--

LOCK TABLES `mfe - sections` WRITE;
/*!40000 ALTER TABLE `mfe - sections` DISABLE KEYS */;
INSERT INTO `mfe - sections` VALUES (1,'MFE-1A',1,42),(2,'MFE-1B',1,42),(3,'MFE-1C',1,42),(4,'MFE-2A',2,42),(5,'MFE-2B',2,42),(6,'MFE-3A',3,42),(7,'MFE-3B',3,42),(8,'MFE-4A',4,42),(9,'MFE-4B',4,42);
/*!40000 ALTER TABLE `mfe - sections` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `mfe - subjects`
--

DROP TABLE IF EXISTS `mfe - subjects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `mfe - subjects` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `Code` varchar(45) NOT NULL,
  `Course Name` varchar(150) NOT NULL,
  `No. of Units` int NOT NULL,
  `Subject Type` varchar(45) NOT NULL,
  `Total Hours` int NOT NULL,
  `Year Level` int NOT NULL,
  `Semester` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=91 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `mfe - subjects`
--

LOCK TABLES `mfe - subjects` WRITE;
/*!40000 ALTER TABLE `mfe - subjects` DISABLE KEYS */;
INSERT INTO `mfe - subjects` VALUES (1,'MMW 101','Mathematics in the Modern World',3,'Lecture',3,1,1),(2,'UTS 101','Understanding the Self',3,'Lecture',3,1,1),(3,'PAL 101','Panitikan at Lipunan',3,'Lecture',3,1,1),(4,'PCM 101','Purposive Communication',3,'Lecture',3,1,1),(5,'ETH 101','Ethics',3,'Lecture',3,1,1),(6,'COE 100','Mathematics for Engineers',3,'Lecture',3,1,1),(7,'COE 101','Introduction to Engineering',1,'Lecture',1,1,1),(8,'COE 102','Calculus 1',3,'Lecture',3,1,1),(9,'COE 103','Chemistry for Engineers',3,'Lecture',3,1,1),(10,'COE 103L','Chemistry for Engineers Laboratory',1,'Lab',3,1,1),(11,'PE 10','PATHFIT 1',2,'Lecture',2,1,1),(12,'NSTP 10','NSTP',3,'Lecture',3,1,1),(13,'TCW 101','The Contemporary World',3,'Lecture',3,1,2),(14,'RPH 101','Readings in Philippine History',3,'Lecture',3,1,2),(15,'AAP 101','Art Appreciation',3,'Lecture',3,1,2),(16,'COE 104','Calculus 2',3,'Lecture',3,1,2),(17,'COE 105','Physics for Engineers Lecture',3,'Lecture',3,1,2),(18,'COE 105L','Physics for Engineers Laboratory',1,'Lab',3,1,2),(19,'MFE 101','Introduction to Manufacturing Engineering',2,'Lecture',2,1,2),(20,'MFE 102','Workshop Theory and Practices',1,'Lab',3,1,2),(21,'MFE 103','Engineering Drawing',1,'Lab',3,1,2),(22,'MFE 104L','Computer Fundamentals and Programming',1,'Lab',3,1,2),(23,'PE 11','PATHFIT 2',2,'Lecture',2,1,2),(24,'NSTP 11','NSTP 2',3,'Lecture',3,1,2),(25,'AE 101','Academic English',3,'Lecture',3,2,1),(26,'COE 201','Differential Equation',3,'Lecture',3,2,1),(27,'MFE 201 ','Statics of Rigid Bodies',3,'Lecture',3,2,1),(28,'MFE 202','Thermodynamics for Manufacturing',3,'Lecture',3,2,1),(29,'MFE 203','Metrology',1,'Lab',3,2,1),(30,'MFE 204','Basic Electrical Engineering',2,'Lecture',2,2,1),(31,'MFE 204L','Basic Electrical Engineering Laboratory',1,'Lab',3,2,1),(32,'MFE 205','Engineering Economics',3,'Lecture',3,2,1),(33,'MFE 206','Occupational Safety and Health',3,'Lecture',3,2,1),(34,'MFE 207','Machine Shop Practice',1,'Lab',3,2,1),(35,'MFE 208','Computer Aided Drafting',1,'Lab',3,2,1),(36,'PE 12','PATHFIT 3',2,'Lecture',2,2,1),(37,'STS 101','Science, Technology, and Society',3,'Lecture',3,2,2),(38,'MFE 209','Manufacturin Processes 1',1,'Lecture',1,2,2),(39,'MFE 209L','Manufacturin Processes 1 Lab',1,'Lab',3,2,2),(40,'MFE 210','Basic Electronics',2,'Lecture',2,2,2),(41,'MFE 210L','Basic Electronics Lab',1,'Lab',3,2,2),(42,'MFE 211','Advanced Math for MFE with Numerical Methods',3,'Lecture',3,2,2),(43,'MFE 211L','Advanced Math for MFE with Numerical Methods Lab',1,'Lab',3,2,2),(44,'MFE 212','Dynamics of Rigid Bodies',2,'Lecture',2,2,2),(45,'MFE 213','Computer Aided Engineering',1,'Lecture',1,2,2),(46,'MFE 213L','Computer Aided Engineering Lab',1,'Lab',3,2,2),(47,'MFE 214','Motion and Time Study',2,'Lecture',2,2,2),(48,'MFE 215','Manufacturing Engineering Elective 1',3,'Lecture',3,2,2),(49,'PE 13','PATHFIT 4',2,'Lecture',2,2,2),(50,'MFE 301','Mechanics of Deformable Bodies',3,'Lecture',3,3,1),(51,'MFE 302','Fluid Mechanics',2,'Lecture',2,3,1),(52,'MFE 303','Kinematics of Machineries',3,'Lecture',3,3,1),(53,'MFE 303L','Kinematics of Machineries Lab',1,'Lab',3,3,1),(54,'MFE 304','Computer - Aided Manufacturing',1,'Lecture',1,3,1),(55,'MFE 304L','Computer - Aided Manufacturing Lab',1,'Lab',3,3,1),(56,'MFE 305','Engineering Management',3,'Lecture',3,3,1),(57,'MFE 306','Engineering Data Analysis',3,'Lecture',3,3,1),(58,'MFE 307','Manufacturing Processes 2',1,'Lecture',1,3,1),(59,'MFE 307L','Manufacturing Processes 2 Lab',1,'Lab',3,3,1),(60,'SSP 101d','Entrepreneurial Mind',3,'Lecture',3,3,1),(61,'MFE 308L','Microcontroller/Microproce ssor for MFE Lab',1,'Lab',3,3,2),(62,'MFE 309','Material Science and Engineering',2,'Lecture',2,3,2),(63,'MFE 309L','Material Science and Engineering Lab',1,'Lab',3,3,2),(64,'MFE 310','Design Of Machine Elements',3,'Lecture',3,3,2),(65,'MFE 311','Design Of Jigs & Fixtures',3,'Lecture',3,3,2),(66,'MFE 312','Methods of Research',2,'Lecture',2,3,2),(67,'MFE 313','Ergonomics',3,'Lecture',3,3,2),(68,'MFE 314','Engineering Ethics, Codes and Standards',3,'Lecture',3,3,2),(69,'MFE 315','Manufacturing Engineering Elective 2',3,'Lecture',3,3,2),(70,'RLW 101','Life and Works of Rizal',3,'Lecture',3,3,2),(71,'MFE 401D','Project Study 1',1,'Lab',3,4,1),(72,'MFE 402','Technopreneurship',3,'Lecture',3,4,1),(73,'MFE 403','Design of Machineries',1,'Lecture',1,4,1),(74,'MFE 403L','Design of Machineries Lab',1,'Lab',3,4,1),(75,'MFE 404','Computer-Integrated Manufacturing',1,'Lecture',1,4,1),(76,'MFE 404L','Computer-Integrated Manufacturing Lab',1,'Lab',3,4,1),(77,'MFE 405','Engineering Production and Management',3,'Lecture',3,4,1),(78,'MFE 406','Instrumentation and Control',2,'Lecture',2,4,1),(79,'MFE 406L','Instrumentation and Control Lab',1,'Lab',3,4,1),(80,'MFE 407','Environmental Science & Engineering',3,'Lecture',3,4,1),(81,'MFE 408','Manufacturing Engineering Elective 3',3,'Lecture',3,4,1),(82,'MFE 409D','Project Study 2',1,'Lab',3,4,2),(83,'MFE 410','Mechatronics',2,'Lecture',2,4,2),(84,'MFE 410L','Mechatronics Lab',1,'Lab',3,4,2),(85,'MFE 411','Plant Visits and Seminars',1,'Lab',3,4,2),(86,'MFE 412','Lean Manufacturing',3,'Lecture',3,4,2),(87,'MFE 413','Project Design',3,'Lecture',3,4,2),(88,'MFE 413D','Product Design Lab',1,'Lab',3,4,2),(89,'MFE 414','Comprehensive Examination',1,'Lab',3,4,2),(90,'MFE 415','Manufacturing Engineering Elective 4',3,'Lecture',3,4,2);
/*!40000 ALTER TABLE `mfe - subjects` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(45) NOT NULL,
  `password` varchar(45) NOT NULL,
  `role` varchar(45) NOT NULL,
  `reference id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'admin','password','administrator',142067);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-10-24  3:07:31
